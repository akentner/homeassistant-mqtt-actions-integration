# Phase 9: v1.0.1 Release - Context

**Gathered:** 2026-10-12
**Status:** Ready for planning

<domain>
## Phase Boundary

v1.0.1 becomes a real release. The commit that bumps `custom_components/mqtt_actions/manifest.json` to `1.0.1` passes UAT-02 and UAT-04 on the bench (ha-a, ha-b) on exactly that SHA. That SHA is tagged `v1.0.1` (the user pushes the tag), the release workflow is green, and GitHub/HACS show v1.0.1 as latest. This closes ACCEPTED-GAP-V101 for that release (REL-01).

No product code changes. A failed bench check is a gap; its fix goes into an inserted Phase 9.1, followed by a new bench run on the new SHA.

</domain>

<decisions>
## Implementation Decisions

### Branch strategy
- **D-01:** Freeze `main` until the tag. Bump, bench run and tag all happen on `main`, and Phase 10 starts only after the tag exists. Until then, only `.planning/` commits land on `main`. No `release/1.0.1` branch and no merge-back.
- **D-02:** The tag goes on the bump commit itself, the exact SHA the bench verified. Evidence, ledger and STATE commits come after the bump commit and are not part of the tagged tree. Tag SHA == bench SHA == bump SHA. — **Reversibility:** one-way — A pushed public tag that HACS has offered cannot be moved without breaking installs that resolved it.
- **D-03:** The bump commit changes only `manifest.json` `version` from `1.0.0` to `1.0.1`. There is no `[ci skip]` in the message.
- **D-04:** The order of pushes, done by the user: push `main` first, wait until `ci.yml` and `validate.yml` are green on the bump SHA (Claude checks with `gh run list`), then push the tag `v1.0.1`. This avoids a red release run with a dangling tag.
  - **Amendment (2026-10-12, owner-approved, v1.0.1 only):** CI evidence on the bump SHA counts with `event == "workflow_dispatch"` as well as `"push"`; `headSha` must still equal the bump SHA exactly. Reason: `ci.yml` and `validate.yml` define `on.push` with only `tags-ignore`, so GitHub never runs them for branch pushes (since 2f786d8, plan 04-01). The owner dispatched CI 38299461144 and Validate 38299494978 on main == 7baec98; both green. Record: `09-evidence/release/d04-amendment.txt`. Trigger fix (`branches: ["**"]`) follows after the tag: `.planning/todos/pending/2026-10-12-ci-push-trigger-branches.md`.

### Bench scope and start state
- **D-05:** The bench runs only UAT-02 and UAT-04, as REL-01 requires. UAT-03, P1-5 and the remaining scripted checks are not re-run here; the full re-verification is Phase 12 (QLT-01, QLT-04).
- **D-06:** UAT-04 starts from the restored null-tombstone state, as in plan 08-18. The four registry records of Lampe Test (switch) and Bar Select (select) on ha-a and ha-b are flipped back to `disabled_by: null` after UAT-02, because the guard build turns them into `integration`. The state is proven by a `prepare.txt` state line before the run, in the same format as `uat-04-rerun2/prepare.txt`. This is the hardest case, the one the first v1.0.1 run failed on.
- **D-07:** ha-c (the v0.1.0 straggler, only needed for UAT-01) stays stopped. UAT-02 and UAT-04 run on ha-a and ha-b, as in Phase 8. The roadmap's "ha-a, ha-b, ha-c" refers to the bench as a whole.
- **D-08:** Preflight works like Phase 8. Run `preflight.sh`, take backups of `core.entity_registry` for ha-a and ha-b with both stopped (`~/ha-test/_backup-pre-phase9-<ts>`, mode 0700), and prove that the mounted `custom_components` tree is byte-identical to the bump SHA (pin check in `lib.sh`). The SHA goes into the evidence.
- **D-09:** The expected values of UAT-02 (E1 to E4) and UAT-04 (X1 to X10) stay unchanged from Phase 8. They are coded in the check scripts before anything is observed. The scripts' check logic is not edited; only path or phase parametrization may change (see code_context).

### Release notes
- **D-10:** Release notes are written by hand in English and stored as `09-evidence/release-notes.md`. `release.yml` stays unchanged (`--generate-notes`). Once the release workflow is green, the user applies them with `gh release edit v1.0.1 --notes-file <path>`, or Claude does it with the user's go.
- **D-11:** Required content:
  - the v1.0.1 fixes: the native entity residual fixes (MIG-04 sticky native flag for mirrors, MIG-05 replay catch for late legacy Discovery) and the duplicate guard against enabled core MQTT duplicates of native devices;
  - the behavior change: core MQTT duplicates of native devices are disabled automatically, and a duplicate the user re-enables is disabled again at the next start (README coverage follows in Phase 10, FIX-05);
  - the known limit WR03-LIVE-REPLAY: a live replay of legacy Discovery creates `_2` entities that disappear only after the next start;
  - an upgrade note: no breaking change, update from 1.0.0 via HACS, minimum HA still 2026.9.0.

### Evidence and gap closure
- **D-12:** Evidence follows the Phase 8 pattern: a ledger `09-UAT.md` with one row per check (check, result, date, bump SHA, evidence path), plus raw data in `09-evidence/` (`preflight/`, `uat-02/`, `uat-04/`, `release/`, `release-notes.md`).
- **D-13:** Closing ACCEPTED-GAP-V101 is recorded in:
  - `.planning/PROJECT.md`: the Key Decision row "Close v1.0.1 with an accepted verification gap" changes from "⚠️ Revisit" to closed, with SHA, tag and date, and the status paragraph ("v1.0.1 is not released or tagged") is updated;
  - `.planning/MILESTONES.md`: the v1.0.1 entry gets released, tag, SHA and gap closed (the archived Phase 8 files are not edited);
  - `.planning/STATE.md`: the Phase 9 blocker is removed. The deferred item `07-VERIFICATION.md human_needed` stays, because it belongs to Phase 12 / QLT-01.
- **D-14:** Phase 9 is done only after the user has pushed the tag, `release.yml` is fully green (check-version, CI tiers, hassfest, HACS, release job), GitHub shows v1.0.1 as Latest, and the notes are applied. Claude verifies with `gh run list` / `gh run view` and `gh release view v1.0.1` and stores the output in `09-evidence/release/`.

### Claude's Discretion
- Plan split and wave order (for example: bump + preflight → bench run → ledger/notes → post-tag release check).
- Helper script names and evidence file naming inside `09-evidence/`.
- How the bench scripts are parametrized for the Phase 9 evidence path (env var vs. argument), as long as check logic and expectations stay byte-identical.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and requirements
- `.planning/ROADMAP.md` § Phase 9 — goal, success criteria 1 to 3, notes (user pushes tag, failed check → Phase 9.1)
- `.planning/REQUIREMENTS.md` — REL-01
- `.planning/PROJECT.md` — Key Decisions (D-08 waiver, ACCEPTED-GAP-V101 row) and status paragraph
- `.planning/RETROSPECTIVE.md` — v1.0.1 lessons (stale reports after late fixes; owner decisions get IDs)

### Phase 8 bench run (the pattern to repeat)
- `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-CONTEXT.md` — D-01 to D-08 (bench, automation split, evidence, failure rule)
- `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-UAT.md` — ledger format; blocks 2 (UAT-02) and 4 (UAT-04); observations; decision IDs (UAT04-GAP-DISPOSITION, D08-WAIVER, UAT04-RECEIVER-GUARD, WR03-LIVE-REPLAY)
- `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-18-PLAN.md` and `08-18-SUMMARY.md` — the final re-run including the null-tombstone restore
- `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-evidence/uat-02-rerun2/`, `uat-04-rerun2/` (especially `prepare.txt`, `verdict.txt`) — reference evidence on build `b8232252`
- `.planning/milestones/v1.0.1-REQUIREMENTS.md` — UAT-02 and UAT-04 wording

### Release mechanics
- `.github/workflows/release.yml` — check-version (tag == manifest), ci + validate, `gh release create --generate-notes`
- `.github/workflows/ci.yml`, `.github/workflows/validate.yml` — gates that must be green on the bump SHA before the tag push
- `custom_components/mqtt_actions/manifest.json` — `version` (currently `1.0.0`)
- `hacs.json` — HACS floor 2026.9.0 (unchanged)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `~/ha-test/bin/check-uat02.sh`, `check-uat04.sh`: the scripted checks with the coded expectations (exit 0 PASS, 1 FAIL, 2 ABORT = bench problem).
- `~/ha-test/bin/preflight.sh`, `check-preflight.sh`: bench preflight.
- `~/ha-test/bin/lib.sh`: the pin check (`mount_clean`, `PIN_SHA`) proving that the mounted tree is byte-identical to the SHA.
- `~/ha-test/bin/reseed-tombstones.sh`, `repin-rerun2.sh`: the restore of the null-tombstone state and the pin used in 08-18.
- `~/ha-test/bin/check-evidence-clean.sh`: evidence hygiene.
- `~/ha-test/_backup-*`: the existing backup naming pattern.

### Established Patterns
- Expectations are coded in the script header before observation (D-08 of Phase 8). Superseded runs stay untouched as history; re-runs get a new folder.
- Scrubbed copies of the check scripts are stored next to the evidence, and identity is proven by `cmp` (08-18 Task 1).
- Known bench defect: `check-uat03.sh` leaves a background `mosquitto_sub` running. It does not apply here because UAT-03 is not run, but no stray subscribers should remain.

### Integration Points
- **`~/ha-test/bin/lib.sh:9` hardcodes `PHASE_DIR_REL=".planning/phases/08-real-instance-verification"`, and line 49 builds `08-evidence` from it.** Phase 8 is archived under `.planning/milestones/v1.0.1-phases/`, so the scripts must be pointed at `.planning/phases/09-v1-0-1-release/09-evidence` before the run. This changes bench tooling, not product code, and the check logic stays unchanged (D-09).
- Bench state: ha-a and ha-b registries carry Phase 8 history (tombstones of retired fixture ids, harmless per the 08-UAT Observations). Mosquitto `mosq` StartedAt anchor: re-check after any host reboot.
- Owner follow-up from Phase 8: keep the bench and its tokens until Phase 12.

</code_context>

<specifics>
## Specific Ideas

- The bump SHA is the single anchor: bench evidence, the pin check, CI runs before the tag, the tag itself and the release workflow all name the same SHA.
- Release notes are user-facing and in English. They mention the guard's re-disable behavior even though the README update follows in Phase 10.

</specifics>

<deferred>
## Deferred Ideas

- README and troubleshooting text for the re-disabled duplicate: Phase 10 (FIX-05).
- Full re-verification of Phases 1 to 8 and the UAT-03/P1-5 re-runs: Phase 12 (QLT-01, QLT-04).
- Switching `release.yml` to a notes file instead of `--generate-notes`: not now. Revisit for v1.1.0 if hand-editing after the release proves awkward.

</deferred>

---

*Phase: 09-v1-0-1-release*
*Context gathered: 2026-10-12*
