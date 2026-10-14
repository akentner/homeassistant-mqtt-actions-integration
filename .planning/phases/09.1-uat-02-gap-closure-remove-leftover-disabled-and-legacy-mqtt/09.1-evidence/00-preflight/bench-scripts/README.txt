Scrubbed copy of the bench scripts Phase 9.1 runs (plan 09.1-03 Task 1, 2026-10-14)

source: ~/ha-test/bin/ on the bench host (outside the repository)
copied: check-uat02.sh, check-uat04.sh, check-preflight.sh, preflight.sh, lib.sh, check-evidence-clean.sh,
  check-stale-anchor.sh, check-marker.sh, bench-users.sh, ha-test-guard, reseed-tombstones.sh, ha-test-ws.py and phase9.1.env

one change against Phase 9 (D-11): check-uat02.sh, the comparison path of do_clean only. The live side of the comparison
  already removed the "UAT Marker" rows (unique id starting with MARKER_ID from .fixtures.env); the baseline side did not, so
  clean reported "mqtt_actions rows (without hub rows) differ from the baseline" on a correct bench whose baseline holds the
  marker rows (Phase 9 UAT, Observations, "Bench-tooling defect"). The baseline side now gets the same marker filter, and the
  comment above it says that the marker rows are removed from both sides. No expectation (E1 to E4) changed, no line outside
  do_clean changed. The diff against the Phase 9 copy is check-uat02.diff.

unchanged: the ten scripts check-uat04.sh, check-preflight.sh, preflight.sh, lib.sh, check-evidence-clean.sh,
  check-stale-anchor.sh, check-marker.sh, bench-users.sh, ha-test-guard and reseed-tombstones.sh are byte-identical to the
  Phase 9 copies in .planning/phases/09-v1-0-1-release/09-evidence/00-preflight/bench-scripts/.

proof: cmp-proof.txt. Every script here is cmp-identical to ~/ha-test/bin/; the ten unchanged ones are cmp-identical to the
  Phase 9 copies; check-uat02.sh with do_clean stripped is identical to the Phase 9 copy (the run, live and helper paths are
  byte-identical); the shellcheck findings are those of the Phase 9 copy; clean against the Phase 9 baseline reports the
  "differ from the baseline" line before the edit and no longer after it.

ha-test-ws.py: taken from the Phase 9 copy (itself the Phase 8 copy), which keeps its one documented scrub (the WebSocket
  auth key is written as two adjacent string literals so the scanner's forbidden-key rule does not match; behaviour is
  identical). The original in ~/ha-test/bin/ would trip the scanner and is never copied.

evidence root: lib.sh is not edited. Every bench call sources ~/ha-test/phase9.1.env (copy: phase9.1.env, paths only, no
  secret), which exports PHASE8_EVIDENCE_ROOT=.../.planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-
  legacy-mqtt/09.1-evidence (honoured by evidence_root() in lib.sh), leaves PHASE8_EV_SUFFIX unset and sets
  RESEED_EV_DIR=uat-04 and RESEED_BACKUP_POINTER=$HOME/ha-test/.current-backup-phase9.1.
  Call form: bash -c '. ~/ha-test/phase9.1.env && ~/ha-test/bin/<script> <args>' from the repository root.

folders (user decision 1):
  uat-02/        run (a), the integration start (tombstones disabled_by integration); PHASE8_EV_SUFFIX unset.
                 reseed-tombstones.sh and check-uat04.sh read this folder, with the suffix forced off. This is D-16's
                 uat-02-integration/, under the name the unchanged scripts use.
  uat-02-null/   run (b), the null start (tombstones disabled_by null); PHASE8_EV_SUFFIX=-null for that run only.
  uat-04/        UAT-04 and the prepare.txt of reseed-tombstones.sh (RESEED_EV_DIR=uat-04).
  00-preflight/  D-16's preflight/ folder, under the fixed name the unchanged scripts use (Phase 9 precedent).

never copied, on purpose (T-09.1-12): ~/ha-test/.mqtt-uat.env (the env file with the broker passwords), ~/ha-test/.token-*,
  every .storage directory, every backup directory (~/ha-test/_backup-*), the instance directories a, b, c and the broker
  directory.

scan: ~/ha-test/bin/check-evidence-clean.sh over this directory prints PASS before the commit.
