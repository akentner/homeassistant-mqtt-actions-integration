# Milestones

## v1.0.1 Hardening (Shipped: 2026-10-11)

**Phases completed:** 3 phases (6 to 8), 25 plans
**Timeline:** 9 days (2026-10-03 → 2026-10-11), 177 commits
**Code:** about 9,500 lines of Python in `custom_components/mqtt_actions`; 21 files and about 2,100 lines changed across package, tests, CI and docs
**Releases:** none. v1.0.1 is not tagged (owner decision ACCEPTED-GAP-V101: no release before a bench re-run of UAT-02 and UAT-04 on the final build). Only the `v1.0.1-rc1` prerelease run of Phase 7 existed, and it was removed again.
**Requirements:** 6 of 9 checked off (QLT-01 to QLT-03 open in the traceability, see Known Gaps)

**Delivered:** The v1.0 residuals are closed in the code: native mirrors stay native near the size limit, a boot-time legacy Discovery replay leaves no working duplicate, CI and release run on a pinned runner, the test suite is deterministic, and the four skipped Phase 5 UAT checks pass on real instances, with a receiver-side duplicate guard added on the way.

**Key accomplishments:**
- Native flag as a persisted set of device ids (Phase 6, MIG-04): a native mirror stays native after a restart even at `MAX_DOCUMENT_BYTES`; 1.0.0 Stores still load native.
- Registry-only replay catch (Phase 6, MIG-05): a replayed retained legacy Discovery leaves no `_2` duplicate after the takeover; migrated entities keep registry ids and entity ids.
- Pinned CI and deterministic tests (Phase 7, QLT-02, QLT-03): all eight jobs on `ubuntu-24.04` with a guard test; the flake class fixed at its cause (unscoped `caplog`), three local plus three CI full runs green, `v1.0.1-rc1` release run green end to end.
- Real-instance UAT (Phase 8, UAT-01 to UAT-04): straggler v0.1.0 next to the native fleet, replay with two restarts, exactly-once commands on two instances, Discovery export shape; UAT-04 passes on the receiver-guard build after two failing runs.
- Duplicate guard on every native instance (Phase 8, plans 08-12 and 08-17): core-prefix duplicates are disabled, not removed; after the second code review a disabled MQTT row is never removed (core would clear the retained topic of a foreign export) and user-customized rows are kept.

**Closeout:** override_closeout under owner decision ACCEPTED-GAP-V101 (2026-10-11, recorded in `v1.0.1-phases/08-real-instance-verification/08-UAT.md`, section "Known limitations at milestone close"). `init.manager` reads Phases 6 and 8 as stale and Phase 7 as human_needed after the late review fixes to `takeover.py`, `manager.py` and `tests/`; the archived Phase 1 to 4 reports read stale as well. Accepted as tech debt, not re-verified; the full re-verification moves to the end of v1.1.

Known verification overrides: 1 newly acknowledged, 0 carried forward from a prior close (see STATE.md Deferred Items)

### Known Gaps
- **QLT-01** (Phases 1 to 4 have a current verification): partial. Phase 7 verification rated it partial; the reports read stale again after the Phase 8 review fixes.
- **QLT-02, QLT-03**: satisfied per `07-VERIFICATION.md` (on sha `d92b87f`), but left unchecked in the traceability because Phase 7 never reached `passed` and the later Phase 8 code changes were not run three times on CI.
- **Phase 8 review fixes (CR-01, WR-01 to WR-03, commits `612b0b7` to `31d6e5a`)**: evidenced by unit tests only (1535 passed, 2 xfailed); UAT-02 and UAT-04 not re-run on the final build.

**Known deferred items:**
- Accepted behavior change (CR-01): disabled MQTT duplicates stay in the registry instead of being removed.
- Accepted detection limits: entity-id rename (D2) and assistant exposure `should_expose` (D3) are not recognized as customization (strict xfail tests).
- To v1.1: info findings IN-01 to IN-04 of the first Phase 8 review and IN-01 to IN-03 of the second (incl. a Repairs hint for two customized rows), backlog 999.1.
- Owner follow-ups from `08-UAT.md`: revoke the three bench tokens, tear down the bench state.
- WR-03 (forged retained `offline` lifts a cutover block) stays an accepted limit until the EMQX migration.
- Two v1.0 quick tasks remain unarchived in `.planning/quick/`.

**Archive:** `milestones/v1.0.1-ROADMAP.md`, `milestones/v1.0.1-REQUIREMENTS.md`, `milestones/v1.0.1-phases/`

---

## v1.0 MVP (Shipped: 2026-10-03)

**Phases completed:** 5 phases, 42 plans, 103 tasks
**Timeline:** 6 days (2026-09-28 → 2026-10-03), 327 commits
**Code:** about 9,200 lines of Python in `custom_components/mqtt_actions`; 90 files and about 35,800 lines added across package and tests
**Releases:** v0.1.0 (Phase 1 to 4) and v1.0.0 (adds Phase 5, native entities)
**Requirements:** 51 of 51 complete

**Delivered:** A HACS-installable Home Assistant integration in which a Switch or Select created in the UI runs its actions locally on every instance that shares the MQTT broker, with owner/follower ownership, an approval gate for remote actions, operating tools, and native entities as the default.

**Key accomplishments:**
- Walking skeleton (Phase 1): HACS-shaped repo, hub and subentry flows, a Switch that runs a locally executed Script on MQTT state changes, with retained replays only moving the baseline.
- Select devices and reliable execution (Phase 2): per-option actions, run modes (queued, restart), test buttons per trigger, and a per-device circuit breaker.
- Central config, ownership and trust gate (Phase 3): retained, versioned, sha256-stamped config documents, owner-pinned read-only mirrors, and remote actions run only after the user approves the exact hash.
- Operations, recovery and release (Phase 4): roster and heartbeat, resync, export/import, diagnostics, re-trigger service, adoption of an offline owner's devices, three test tiers and a tag-triggered release workflow.
- Native entities instead of MQTT Discovery (Phase 5): takeover of legacy entities with every registry identity intact, cutover only when no online peer is a legacy instance, optional Discovery export (ADR 0001).
- Security: Phase 5 threat audit closed 19 of 19 threats (`05-SECURITY.md`), the broker trust model and per-instance ACLs are documented.

**Closeout:** override_closeout. `init.manager` rated the verification of Phases 1 to 4 as stale, although their VERIFICATION.md files say `passed`. Proceeded by explicit user choice. Phase 5 is verified `passed`.

**Known deferred items:**
- Phase 5 UAT tests 4 to 7 skipped by the owner (straggler v0.1.0 instance, late replay race, commands across two real instances, Discovery export on/off).
- Accepted review residuals: WR-03 (forged retained `offline` can lift a cutover block), IN-02 (native marker dropped near the document size limit), IN-03 (takeover can race a boot-time retained replay). Documented in README Limitations.
- Backlog 999.1: per-instance local actions on mirrored devices.
- Two quick tasks remain unarchived in `.planning/quick/`.

**Archive:** `milestones/v1.0-ROADMAP.md`, `milestones/v1.0-REQUIREMENTS.md`, `milestones/v1.0-phases/`

---
