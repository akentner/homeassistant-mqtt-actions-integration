# Roadmap: MQTT Actions Integration

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-10-03)
- ✅ **v1.0.1 Hardening** — Phases 6-8 (closed 2026-10-11 with accepted gap, not released)
- 🚧 **v1.1 Local Actions on Mirrors** — Phases 9-12 (in progress)

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

### 🚧 v1.1 Local Actions on Mirrors (In Progress)

**Milestone Goal:** Follower instances can give mirrored devices their own local actions. Before that, v1.0.1 is released properly; after it, the open Phase 8 review findings are closed, and the milestone ends with a full re-verification and a v1.1.0 release. Phase numbering continues from v1.0.1.

**Ordering rationale (owner-fixed 2026-10-11):** The v1.0.1 tag must point at bytes that the bench verified, so Phase 9 comes before any IN-04 or MIR-01 commit on `main`. The IN-04 extraction in Phase 10 moves about 330 lines out of `manager.py`; a pure move is only verifiable on a quiet file, so it lands before MIR-01 edits the same file. MIR-01 (Phase 11) is one vertical slice from storage and runner to the options flow and docs (coarse granularity). Phase 12 comes last because any later fix makes the reports stale again (lesson of v1.0 and v1.0.1). TDD mode is on: each fix and feature starts with a failing test commit.

- [ ] **Phase 9: v1.0.1 Release** - The build whose manifest says 1.0.1 passes UAT-02 and UAT-04 on the bench on exactly that SHA and is published as v1.0.1
- [ ] **Phase 9.1: UAT-02 Gap Closure** (INSERTED) - Replay leaves no disabled or legacy mqtt rows, and UAT-02 and UAT-04 pass on the new SHA
- [ ] **Phase 10: Review Findings and Native Migration Extraction** - The Phase 8 info findings are closed, and the start-up migration orchestration lives in its own module outside `manager.py`
- [ ] **Phase 11: Local Actions on Mirrors** - A follower sets its own actions per trigger of a mirrored device; they run locally under the device's gates and never reach the broker
- [ ] **Phase 12: Re-verification and v1.1.0 Release** - Every phase has a current verification, the bench checks pass on the final SHA, and v1.1.0 is published

## Phase Details

### Phase 9: v1.0.1 Release

**Goal**: v1.0.1 becomes a real release: the commit whose manifest says 1.0.1 passes UAT-02 and UAT-04 on the bench on exactly that SHA and is tagged, which closes ACCEPTED-GAP-V101 for that release.
**Depends on**: Phase 8 (v1.0.1 code complete, closed with accepted gap ACCEPTED-GAP-V101)
**Requirements**: REL-01
**Success Criteria** (what must be TRUE):
  1. The manifest bump to 1.0.1 is committed before the bench run, and the commit to be tagged contains no IN-04 or MIR-01 change: either `main` stays frozen until the tag, or the release is cut from `release/1.0.1` and merged back afterwards. (REL-01)
  2. UAT-02 and UAT-04 pass on the bench (ha-a, ha-b, ha-c) on exactly that SHA; the evidence records the SHA and records ACCEPTED-GAP-V101 as closed for v1.0.1. (REL-01)
  3. After the user pushes the tag `v1.0.1`, the release workflow (check-version, the three test tiers, hassfest, HACS validation, release job) is green, and GitHub shows v1.0.1 as the latest release, so HACS offers 1.0.1. (REL-01)

**Plans**: 3/5 plans executed

Plans:
**Wave 1**
- [x] 09-01-PLAN.md — Bump commit on main, bench pinned to the bump SHA (tracer), bench scripts proven unchanged, push readiness

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 09-02-PLAN.md — Owner pushes the bump SHA to main; CI and Validate green on exactly that SHA

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 09-03-PLAN.md — UAT-02 and UAT-04 on the bump SHA (UAT-04 from the restored null-tombstone state), ledger 09-UAT.md, release notes

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 09-04-PLAN.md — Pre-tag gate, owner decision on the one-way tag, owner pushes v1.0.1

**Wave 5** *(blocked on Wave 4 completion)*
- [ ] 09-05-PLAN.md — Release run green, Latest, notes applied; ACCEPTED-GAP-V101 closed in ledger, PROJECT, MILESTONES, STATE

**Notes**:
- The user pushes the tag. Claude prepares the bump commit, the bench run and the evidence.
- Standard patterns, no research needed (release mechanics: research PITFALLS 10 and RETROSPECTIVE). No `[ci skip]` in squashed commits.
- A failed bench check is a gap, not an accepted skip. Its fix goes into an inserted Phase 9.1 on the release line, followed by a new bench run on the new SHA; no product fixes inside this verification phase (PROJECT.md Key Decision on the D-08 waiver).

### Phase 09.1: UAT-02 gap closure: remove leftover disabled and legacy mqtt rows on replay, then re-run UAT-02 and UAT-04 on a new SHA (INSERTED)

**Goal:** A retained legacy Discovery replay at start leaves no disabled or legacy mqtt rows and no legacy device behind, from integration and from null tombstones, without ever clearing another instance's export (CR-01); UAT-02 (both tombstone states) and UAT-04 pass on the bench on exactly the fix SHA, which the re-pointed plans 09-04 and 09-05 then tag and release as v1.0.1.
**Requirements**: REL-01
**Depends on:** Phase 9
**Success Criteria** (what must be TRUE):
  1. A test that starts from integration tombstones reproduces E1 to E3 before the fix and passes after it. With legacy or empty content on the core-prefix topic the start-up catch removes integration-disabled replay twins and the emptied legacy device; export or unknown content, user-disabled and customized rows stay (D-01 to D-05, D-08). (REL-01)
  2. The owner, and only the owner, clears a stale retained legacy discovery after the catch; a follower publishes nothing (D-06, T-5-02). (REL-01)
  3. The fix SHA is on `main` by fast-forward with manifest 1.0.1, the owner pushed exactly that SHA, and CI and Validate are green on it (D-13 to D-15). (REL-01)
  4. On the bench, the first start of the fix build cleans the leftover rows (D-09), UAT-02 passes from integration and from null tombstones, and UAT-04 passes, all on exactly the fix SHA (D-10 to D-12). (REL-01)
  5. `09-UAT.md` carries the fix-SHA rows, the release notes name the fixed case, and plans 09-04 and 09-05 read the fix SHA (D-16). (REL-01)

**Plans:** 11/12 plans executed

Plans:
**Wave 1**
- [x] 09.1-01-PLAN.md — Product fix, legacy-payload path (tracer, test first): content classifier, sync verdicts, refined disabled branch, owner-only clear of the stale legacy topic

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 09.1-02-PLAN.md — Product fix, empty-topic path: settle signal and grace, count-only log for unknown content, G6 rewrite, broker pin of the retained replay, docs; ends with FIX

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 09.1-03-PLAN.md — check-uat02.sh clean comparison fix (D-11) with run-path proof, phase9.1.env, push readiness of FIX

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 09.1-04-PLAN.md — Owner pushes exactly FIX and dispatches CI and Validate; both green on FIX

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 09.1-05-PLAN.md — Bench pinned to FIX, heal start recorded (D-09), UAT-02 from integration and null tombstones, UAT-04

**Wave 6** *(blocked on Wave 5 completion)*
- [x] 09.1-06-PLAN.md — Ledger rows on FIX, release notes, 09-04 and 09-05 re-pointed to FIX, refined CR-01 rule in PROJECT and STATE

Gap closure (09.1-VERIFICATION.md: the review fixes moved FIX past 681c587; strict serial chain):

**Wave 7** *(blocked on Wave 6 completion)*
- [x] 09.1-07-PLAN.md — Troubleshooting correction (owner decision 1) becomes the new FIX; fix2 bench environment; push readiness of the new FIX

**Wave 8** *(blocked on Wave 7 completion)*
- [x] 09.1-08-PLAN.md — Owner decision and refspec push of the new FIX, dispatch; CI and Validate green with headSha == FIX

**Wave 9** *(blocked on Wave 8 completion)*
- [x] 09.1-09-PLAN.md — Bench pinned to the new FIX, pre-state restored from the pre-9.1 backup (owner decision 2), heal start (tracer), green gate and handoff record

**Wave 10** *(blocked on Wave 9 completion)*
- [x] 09.1-10-PLAN.md — Pin re-asserted from the handoff (same pinned session), UAT-02 from integration and null tombstones, UAT-04, clean bench

**Wave 11** *(blocked on Wave 10 completion)*
- [x] 09.1-11-PLAN.md — CR-01 bench observation on the new FIX (observation only), clean bench

**Wave 12** *(blocked on Wave 11 completion)*
- [ ] 09.1-12-PLAN.md — Ledger blocks 12 to 17 on the new FIX (681c587 superseded), CR-01 exception in the release notes, 09-04 and 09-05 re-pointed to fix2, PROJECT and STATE

### Phase 10: Review Findings and Native Migration Extraction

**Goal**: The info findings of both Phase 8 reviews are closed, and the takeover, replay-catch and duplicate-guard orchestration lives in its own module, so `manager.py` is smaller and quiet before MIR-01 edits it.
**Depends on**: Phase 9 (no IN-04 commit on `main` before the v1.0.1 tag)
**Requirements**: FIX-01, FIX-02, FIX-03, FIX-04, FIX-05, FIX-06, FIX-07, FIX-08
**Success Criteria** (what must be TRUE):
  1. The takeover, replay-catch and duplicate-guard orchestration lives in its own module outside `manager.py`. The move lands as a plan of its own with unchanged behavior, proven by the existing suite and by a start-up ordering test written before the move. (FIX-02)
  2. Tests fail loudly, never skipped or xfailed, when the private registry flush API (`registry._store`, `registry._data_to_save`) disappears or stops writing, and when the no-clear guarantee for loaded rows would silently lose its basis in the HA-internal eager task of `Entity._async_registry_updated` (or the guarantee no longer depends on it). The guard test proves that the listener runs for a second create event and returns 0. Shared test helpers live in one module, and no test module imports private helpers from another test module. (FIX-01, FIX-03, FIX-04, FIX-07)
  3. When a row raises mid-loop in the replay catch, no emptied device is left behind and the partial count is still reported. (FIX-06)
  4. While customized duplicates are kept enabled (including the WR-03 cases), the user sees one non-fixable Repairs warning that lists them, in English and German; it disappears once none remain, and no registry row is ever removed. (FIX-08)
  5. README and troubleshooting state that a duplicate the user re-enables is disabled again at the next start. (FIX-05)

**Plans**: TBD
**Notes**:
- Plan order: the loud registry-API test (FIX-01) and the shared test helpers (FIX-03) first, then the start-up ordering spy test, then the pure move (FIX-02) as a plan of its own. FIX-04 to FIX-08 build on the moved module in separate plans. Never mix the move and a fix in one plan.
- Pure-move discipline (research ARCHITECTURE and PITFALLS 8, 9): keep `@callback` methods synchronous, grep `patch(` targets after the move, run a mutation check per moved function; the only test edit allowed in the move plan is the `_cancel_replay_catch` access.
- Standard patterns, no research needed (collaborator pattern of `SyncManager`, `PresenceManager`, `RetriggerCoordinator`; seams mapped line by line in research ARCHITECTURE).

### Phase 11: Local Actions on Mirrors

**Goal**: On a follower, the user gives a mirrored device its own actions per trigger, in addition to or instead of the owner's actions. They run locally without approval under the device's mode and breaker, survive owner changes, and never leave the instance (MIR-01, backlog 999.1).
**Depends on**: Phase 10 (migration orchestration extracted from `manager.py`, shared test helpers in place)
**Requirements**: MIR-01, MIR-02, MIR-03, MIR-04, MIR-05, MIR-06, MIR-07, MIR-08, MIR-09, MIR-10, MIR-11, MIR-12, MIR-13, MIR-14, MIR-15
**Success Criteria** (what must be TRUE):
  1. On a follower, the user opens the integration's options, picks a mirrored device and a trigger (switch on, switch off or a Select option), chooses "in addition to" or "instead of" and edits the local actions in the action editor; the change applies without a restart, and every new text exists in English and German. (MIR-01, MIR-15)
  2. Local actions run without approval, also while the owner's actions are pending, blocked or empty, and the owner's actions still run only when their exact hash is approved. An empty "instead of" mutes the trigger on this instance. While the owner's actions are unapproved, safe defaults instead of the owner's `run_on_startup`, run mode and breaker limits govern local runs. (MIR-02, MIR-05, MIR-11)
  3. In "in addition to" mode, owner and local parts run in parallel in the device's single Script, and a runtime failure of one part does not stop the other. Device mode (observe, disabled) and the breaker apply to local runs, and a local edit releases a tripped breaker. Test buttons and the re-trigger service run the effective actions on this instance. Local action failures raise their own Repairs issue, independent of owner action failures. (MIR-03, MIR-09, MIR-10, MIR-13)
  4. Nothing local leaves the instance: the central config, actions hash, export, diagnostics content and adoption payload are byte-identical with and without local actions, existing approvals stay valid, and no new re-trigger status or reason word appears on the broker. Diagnostics show only counts of local actions (per device, orphaned). The approval issue says how many triggers are replaced locally, while the approval stays pending and adoption stays refused. (MIR-04, MIR-10, MIR-12, MIR-14)
  5. Local actions survive owner content changes, renames, rev bumps, restarts and an owner re-pin. Local actions of a Select option the owner removed stay inactive, are listed as orphaned in the options where the user can remove them, and re-attach when the same StateValue returns. A tombstone or an adoption discards them with a log entry and `adopt_device` reports it; start-up and transient prunes discard nothing. The README documents modes, mute, parallel semantics, this lifecycle, downgrade behavior and the `{{ state }}` template caveat. (MIR-06, MIR-07, MIR-08, MIR-15)

**Plans**: TBD
**UI hint**: yes
**Research**: needed (`/gsd-plan-phase 11` with research): pin test of `parallel` branch semantics in core 2026.9.4 (`stop`, `continue_on_error`, response variables, re-raise of the first exception after both branches); validating and guarding the owner part (static denylist, `GuardedTemplate`) apart from the unguarded local part before assembly; Store skeleton with its own migrate function; `section` plus `ActionSelector` rendering in an options flow on the 2026.9 frontend (check on the bench early).
**Notes**:
- Owner decisions of 2026-10-11 (record as D-xx in discuss-phase): one Script per mirror with a `parallel` branch for "in addition to" (no separate local Script); discard on tombstone and adoption, logged and reported; orphaned Select options kept inactive and re-attached; no `GuardedTemplate` on local actions (same trust as owned devices); UI is a menu in the hub options flow (no config subentry type, whose unique ids collide across types and break adoption).
- Still open for discuss-phase: storage location (separate Store file, research recommendation, or an additive key in the main Store, which a v1.0.x downgrade drops on its first save; either way the downgrade behavior goes into README and release notes) and the stored trigger identity (StateValue plus device kind recommended). If the `parallel` pin test shows surprises, the owner decides before any fallback to a sequential owner-then-local sequence.
- Plan order: invariant tests first (hash equality, adoption bytes, the 4x3x2 gate matrix of approval state x local mode x owner trigger has actions, a "never published" check across all fake-broker publishes), then the HA-free overlay module and the plan-based runner build (owned devices and overlay-free mirrors assemble byte-identically to today), then the manager wiring (overlays loaded before mirrors are restored, writes under the lock with an immediate save, no start-up garbage collection), then the options flow, texts, approval issue text and README. The flow is a thin client of the manager API.
- Security: add a threat entry "trust-level mixing in one Script" for `/gsd-secure-phase`; `_refuse_denied` and the static denylist apply to the owner part only.
- End the phase with a milestone-wide cross-file review, so every product fix lands before Phase 12.

### Phase 12: Re-verification and v1.1.0 Release

**Goal**: The final v1.1 build is verified end to end and published: every phase has a current verification, the bench checks pass on exactly the tagged SHA, and v1.1.0 is released.
**Depends on**: Phase 11 (all product changes of the milestone done)
**Requirements**: QLT-01, QLT-04, QLT-05, REL-02
**Success Criteria** (what must be TRUE):
  1. Phases 1 to 8 (archived directories) and 9 to 11 have verification reports of the final build, and Phase 12's own verification completes the set: `init.manager` reports none of Phases 9 to 12 as stale, and `verification status` reads current for the archived Phase 1 to 8 directories. (QLT-01)
  2. The manifest bump to 1.1.0 is committed before the bench run, and UAT-02 and UAT-04 pass on the bench on exactly that SHA, which the evidence records. (QLT-04)
  3. On real instances, ha-b adds local actions to a device owned by ha-a in "in addition to" mode, in "instead of" mode and on an owner device without actions; each case runs on ha-b as configured, and nothing local appears on the broker. (QLT-05)
  4. After the user pushes the tag, `v1.1.0` points at a commit newer than `v1.0.1` with manifest 1.1.0, the release workflow, hassfest and HACS are green, and the release notes cover local actions and downgrade behavior. (REL-02)

**Plans**: TBD
**Notes**:
- No product code changes in this phase. A failed check is a gap: its fix goes into an inserted Phase 11.x, then the affected verifications and the bench run are repeated on the new SHA.
- The user pushes the tag.
- Standard patterns, no research needed (repeats the v1.0.1 verification and release process). The v1.1 → v1.0.1 → v1.1 downgrade round trip on the bench is deferred (MIR-F4).

## Progress

**Execution Order:**
Phases execute in numeric order: 9 → 10 → 11 → 12

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 9. v1.0.1 Release | 3/5 | In Progress | - |
| 9.1. UAT-02 Gap Closure (INSERTED) | 11/12 | In Progress | - |
| 10. Review Findings and Native Migration Extraction | 0/TBD | Not started | - |
| 11. Local Actions on Mirrors | 0/TBD | Not started | - |
| 12. Re-verification and v1.1.0 Release | 0/TBD | Not started | - |

## Backlog

No open items. Phase 999.1 (per-instance local actions on mirrored devices) was promoted into milestone v1.1 as MIR-01 to MIR-15 (Phase 11).
