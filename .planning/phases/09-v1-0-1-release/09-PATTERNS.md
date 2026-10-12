# Phase 9: v1.0.1 Release - Pattern Map

**Mapped:** 2026-10-12
**Files analyzed:** 12 (create/modify) + bench tooling
**Analogs found:** 12 / 12 (release notes: partial)

Phase 8 archive root used below: `P8=.planning/milestones/v1.0.1-phases/08-real-instance-verification` (tracked).
Bench tooling `~/ha-test/bin/` is outside the repo (not git-tracked); it is referenced as tooling, never copied into product code.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `custom_components/mqtt_actions/manifest.json` (version 1.0.0 -> 1.0.1) | config | — | itself (line `"version": "1.0.0"`) | exact |
| `09-evidence/preflight/` (build.txt, backup pointer, mount proof, bench-scripts/ copies) | evidence | file-I/O | `$P8/08-evidence/00-preflight/` | exact |
| `09-evidence/uat-02/` | evidence | batch | `$P8/08-evidence/uat-02-rerun2/` | exact |
| `09-evidence/uat-04/` (incl. `prepare.txt`, `verdict.txt`) | evidence | batch | `$P8/08-evidence/uat-04-rerun2/` | exact |
| `09-evidence/release/` (gh run list/view, gh release view output) | evidence | request-response | none (Phase 7 rc1 run was removed) | partial |
| `09-evidence/release-notes.md` | docs | — | none in repo | no analog |
| `09-UAT.md` | ledger | — | `$P8/08-UAT.md` | exact |
| `.planning/PROJECT.md` (line 13 status, line 93 Key Decision row) | docs/state | — | itself | exact |
| `.planning/MILESTONES.md` (v1.0.1 entry, lines 3-37) | docs/state | — | itself | exact |
| `.planning/STATE.md` (Blockers line 236) | docs/state | — | itself | exact |
| `~/ha-test/bin/lib.sh` (evidence path parametrization only) | bench utility | — | itself, `evidence_root()` lines 36-51 | exact |
| `~/ha-test/bin/reseed-tombstones.sh` (prepare.txt target path) | bench utility | file-I/O | itself | exact |

## Pattern Assignments

### `custom_components/mqtt_actions/manifest.json` (bump commit, D-02/D-03)
Last line of the file is `"version": "1.0.0"` -> change only this to `"1.0.1"`. Nothing else in the commit (no `.planning/` changes, no `[ci skip]`). `release.yml` `check-version` job compares it via:
```bash
manifest_version=$(jq -r .version custom_components/mqtt_actions/manifest.json)
tag_version="${GITHUB_REF_NAME#v}"
```
Verify locally: `jq -r .version custom_components/mqtt_actions/manifest.json` == `1.0.1`; `git show --stat HEAD` names only manifest.json.

### Bench path parametrization — `~/ha-test/bin/lib.sh`
Hardcodes (lib.sh:9 and :49):
```bash
PHASE_DIR_REL=".planning/phases/08-real-instance-verification"
...
evidence_root() {
  if [ -n "${PHASE8_EVIDENCE_ROOT:-}" ]; then
    echo "$PHASE8_EVIDENCE_ROOT"
    return
  fi
  ...
  echo "$top/$PHASE_DIR_REL/08-evidence"
}
phase_dir() { echo "$(dirname "$(evidence_root)")"; }
```
Two options (Claude's discretion):
- **Preferred (no edit to lib.sh):** export `PHASE8_EVIDENCE_ROOT=$PWD/.planning/phases/09-v1-0-1-release/09-evidence` for every bench call. lib.sh stays byte-identical to `$P8/08-evidence/00-preflight/bench-scripts/lib.sh` — the `cmp` proof of 08-18 still works unchanged.
- Alternative: edit lines 9/49 to read `${PHASE_DIR_REL:-...}` / an evidence-dir-name variable; then the scrubbed copy differs and the plan must record a `diff` showing only those lines changed.
Also note `PHASE8_EV_SUFFIX` (used in 08-18 with `-rerun2`): leave unset in Phase 9 so folders are `uat-02/`, `uat-04/` per D-12. Check `check-uat02.sh`/`check-uat04.sh` for the suffix handling before the run.
`check-final.sh` (lines 53-54, 115-116) also hardcodes `08-UAT.md`/`08-evidence` — not needed for Phase 9; do not run it.

### `~/ha-test/bin/reseed-tombstones.sh` (D-06 restore)
Header documents behavior (`--check` read-only mode, then the flip). Hardcoded target:
```bash
ER="$(evidence_root)"
PREP="$ER/uat-04-rerun2/prepare.txt"
ID_SWITCH=11111111-aaaa-4aaa-8aaa-000000000001 # Lampe Test
ID_SELECT=b6bd2c0e-6d81-49ea-8025-4bd087bd718a # Bar Select
mkdir -p "$ER/uat-04-rerun2"
```
With `PHASE8_EVIDENCE_ROOT` pointing at 09-evidence, this writes `09-evidence/uat-04-rerun2/prepare.txt`. Either accept that folder name, or change only the `uat-04-rerun2` literal (path-only edit, D-09 allowed) and record the diff. Run `reseed-tombstones.sh --check` first. Note it also runs `check-uat02.sh clean` and `check-preflight.sh --quick` internally.

### `09-evidence/preflight/` (D-08)
**Analog:** `$P8/08-evidence/00-preflight/` (`build.txt`, `backup-manifest.txt`, `mount-hashes.txt`, `bench-scripts/` + `README.txt`).
build.txt shape (from `uat-04-rerun2/prepare.txt`, written by preflight.sh:58ff):
```
sha: <40-hex bump SHA>
branch: main
commit_time: <ISO>
mount_source: .../custom_components/mqtt_actions (read-only bind mount on ha-a and ha-b)
mount_content: byte-identical to the custom_components tree of sha (blob-by-blob, no extra files)
ha_version: 2026.9.4 (a), 2026.9.4 (b)
```
Pin proof: `preflight.sh:25` `if ! diffs=$(mount_clean); then abort ...`; `mount_clean()` at lib.sh:105-125 compares against `git ls-tree -r "$PIN_SHA" -- custom_components`. PIN_SHA is derived from the mounted checkout's HEAD (lib.sh:67-100), so `main` must be checked out at the bump SHA in the mount source. Backups: `~/ha-test/_backup-pre-phase9-<ts>` mode 0700 (existing naming: `_backup-pre-gap-rerun2-20261011T125246Z`).
Scrubbed copies: copy `check-uat02.sh check-uat04.sh lib.sh reseed-tombstones.sh preflight.sh check-preflight.sh` into `09-evidence/preflight/bench-scripts/` and prove expectations unchanged with `cmp` against `$P8/08-evidence/00-preflight/bench-scripts/<s>` (pattern: 08-18-PLAN.md line 143 automated verify).

### `09-evidence/uat-02/` and `09-evidence/uat-04/`
**Analogs:** `$P8/08-evidence/uat-02-rerun2/` (baseline-*.json, round1/2-*.json, log-*.txt, precheck.txt, result.txt, verdict.txt) and `uat-04-rerun2/` (prepare.txt, registry-*.json, post-restart-*, guard-log-*, verdict.txt, ...). Files are produced by the scripts; do not hand-write them.
verdict.txt format (`uat-02-rerun2/verdict.txt`):
```
PASS
E1 to E4 hold in round 1 and round 2 on ha-a and ha-b
build: b8232252540a55969145ca0034d8fd86b4be3b7c
```
prepare.txt state block format (`uat-04-rerun2/prepare.txt`): `== state before ... <ISO>` then per instance `-- ha-a live rows with platform mqtt (entity_id, unique_id, disabled_by), N in total` and `-- ha-a deleted entities ...` with one JSON object per line. Phase 9 must show `"disabled_by":null` for unique_ids `11111111-aaaa-4aaa-8aaa-000000000001` and `b6bd2c0e-6d81-49ea-8025-4bd087bd718a` on both instances before UAT-04.
Order (08-18): preflight --quick -> check-uat02.sh -> reseed-tombstones.sh -> check-uat04.sh. Exit codes: 0 PASS, 1 FAIL (-> Phase 9.1), 2 ABORT (bench problem). Afterwards `check-evidence-clean.sh <folder>` on each folder before commit (T-08-02 hygiene; its default target is the 08 tree, so always pass paths).

### `09-UAT.md` (D-12)
**Analog:** `$P8/08-UAT.md` — frontmatter (`status`, `phase`, `source`, `started`, `updated`), `## Current Test`, `## Build under test` (sha, branch, commit time, image, ha-a/ha-b instance ids), `## Results` table, `## Tests` blocks, `## Summary`, `## Requirement verdicts`.
Results row format (08-UAT.md:45-50):
```
| Check | Requirement or source | Result | Date | Build SHA | Evidence |
| UAT-02 | UAT-02, ROADMAP criterion 2, 05-UAT test 5 | pass | 2026-10-11 | b8232252... | .planning/phases/08-real-instance-verification/08-evidence/uat-02-rerun2 |
```
Phase 9: rows UAT-02, UAT-04 (plus preflight and release rows if desired), Build SHA = bump SHA, Evidence = `.planning/phases/09-v1-0-1-release/09-evidence/<dir>`. Requirement verdict row: REL-01.

### `09-evidence/release/` (D-04, D-14)
No archived analog. Capture raw output of: `gh run list --commit <bump-sha>` (ci.yml + validate.yml green, before tag push), `gh run list --workflow release.yml`, `gh run view <id>` (jobs: check-version, CI, Validate, Create GitHub release), `gh release view v1.0.1`, and `git rev-parse v1.0.1^{commit}` == bump SHA. Run `check-evidence-clean.sh` on it.

### `09-evidence/release-notes.md` (D-10/D-11)
No analog. Content per D-11 (fixes MIG-04/MIG-05 + duplicate guard; behavior change re-disable; known limit WR03-LIVE-REPLAY; upgrade note, min HA 2026.9.0 per `hacs.json`). Applied via `gh release edit v1.0.1 --notes-file .planning/phases/09-v1-0-1-release/09-evidence/release-notes.md`. `release.yml` stays unchanged.

### `.planning/PROJECT.md` (D-13)
- Line 13 status paragraph: "...v1.0.1 is not released or tagged. The last public release stays v1.0.0. A v1.0.1 release needs a bench re-run..." -> state released, tag `v1.0.1`, SHA, date, gap closed.
- Line 69 "Closed v1.0.1 (2026-10-11, not released)" — also stale; update consistently.
- Line 93 row: `| Close v1.0.1 with an accepted verification gap (ACCEPTED-GAP-V101) | ... | ⚠️ Revisit: re-verify and re-run UAT-02/UAT-04 before any release |` -> outcome column closed with SHA, tag, date, pointer to `09-UAT.md`.

### `.planning/MILESTONES.md` (D-13)
v1.0.1 entry line 8: `**Releases:** none. v1.0.1 is not tagged (owner decision ACCEPTED-GAP-V101 ...)` -> released v1.0.1, tag, SHA, date, gap closed by Phase 9. Line 20 Closeout paragraph may get a closing sentence. Do not edit archived `$P8` files.

### `.planning/STATE.md` (D-13)
Remove line 236 under `### Blockers/Concerns` (`- [Phase 9]: No IN-04 or MIR-01 commit on main before the v1.0.1 tag ...`). Keep the `07-VERIFICATION.md human_needed` deferred item.

## Shared Patterns

- **Single anchor SHA:** bump SHA appears in build.txt, verdict.txt `build:` lines, 09-UAT.md rows, `gh run list --commit`, tag, release run.
- **Commit hygiene (D-01/D-02):** only `.planning/` commits after the bump on `main`; evidence commits never amend the bump commit.
- **Secrets:** every evidence folder passes `~/ha-test/bin/check-evidence-clean.sh <path>` before commit; never copy `~/ha-test/.mqtt-uat.env` or tokens.
- **Superseded runs stay:** a FAIL is recorded and stands; any re-run on a new SHA gets a new folder (Phase 9.1 rule).
- **Workflow gates:** `ci.yml`/`validate.yml` trigger on `push`; release.yml calls them as reusable workflows after `check-version`.

## No Analog Found

| File | Role | Reason |
|---|---|---|
| `09-evidence/release-notes.md` | docs | No hand-written release notes exist; all prior releases used `--generate-notes` |
| `09-evidence/release/` | evidence | v1.0.1-rc1 release evidence of Phase 7 was not kept as a folder |

## Metadata
**Search scope:** `$P8/`, `$P8/08-evidence/`, `~/ha-test/bin/`, `.github/workflows/`, `.planning/{PROJECT,MILESTONES,STATE}.md`, manifest.json
**Pattern extraction date:** 2026-10-12
