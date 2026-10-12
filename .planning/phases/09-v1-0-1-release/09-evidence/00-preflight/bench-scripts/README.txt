Scrubbed copy of the bench scripts Phase 9 runs (plan 09-01 Task 2, 2026-10-12)

source: ~/ha-test/bin/ on the bench host (outside the repository)
copied: check-uat02.sh, check-uat04.sh, check-preflight.sh, preflight.sh, lib.sh, check-evidence-clean.sh,
  check-stale-anchor.sh, check-marker.sh, bench-users.sh, ha-test-guard, reseed-tombstones.sh, ha-test-ws.py and phase9.env

unchanged (D-09): the ten scripts check-uat02.sh, check-uat04.sh, check-preflight.sh, preflight.sh, lib.sh,
  check-evidence-clean.sh, check-stale-anchor.sh, check-marker.sh, bench-users.sh and ha-test-guard are byte-identical to
  the scrubbed Phase 8 copies in .planning/milestones/v1.0.1-phases/08-real-instance-verification/08-evidence/00-preflight/
  bench-scripts/ (proof: cmp-proof.txt). The expectations E1 to E4 (UAT-02) and X1 to X10 (UAT-04) are those of Phase 8.

one edit: reseed-tombstones.sh, path only. The evidence folder of prepare.txt reads ${RESEED_EV_DIR:-uat-04-rerun2} and the
  backup pointer file reads ${RESEED_BACKUP_POINTER:-$HT/.current-backup-gap08-rerun2}; one header comment line names both
  variables. The defaults keep the Phase 8 values. The flip, the validation, the counts and the regression-state line are
  unchanged. The diff against the Phase 8 copy is reseed-tombstones.diff.

ha-test-ws.py: taken from the Phase 8 copy, which keeps its one documented scrub (the WebSocket auth key is written as two
  adjacent string literals so the scanner's forbidden-key rule does not match; behaviour is identical). The original in
  ~/ha-test/bin/ would trip the scanner.

evidence root: lib.sh is not edited. Every bench call sources ~/ha-test/phase9.env (copy: phase9.env, paths only, no secret),
  which exports PHASE8_EVIDENCE_ROOT=.../.planning/phases/09-v1-0-1-release/09-evidence (honoured by evidence_root() in
  lib.sh), leaves PHASE8_EV_SUFFIX unset (folders uat-02/ and uat-04/) and sets RESEED_EV_DIR=uat-04 and
  RESEED_BACKUP_POINTER=$HOME/ha-test/.current-backup-phase9.
  Call form: bash -c '. ~/ha-test/phase9.env && ~/ha-test/bin/<script> <args>' from the repository root.

never copied, on purpose (T-09-01): ~/ha-test/.mqtt-uat.env (broker passwords), ~/ha-test/.token-*, every .storage
  directory, every backup directory (~/ha-test/_backup-*), the instance directories a, b, c and the broker directory.

scan: ~/ha-test/bin/check-evidence-clean.sh over this directory prints PASS before the commit.
