# Milestones

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
