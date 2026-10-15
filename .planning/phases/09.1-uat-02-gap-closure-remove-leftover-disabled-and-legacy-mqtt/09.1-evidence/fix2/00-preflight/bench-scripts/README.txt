Bench environment of the Phase 9.1 re-run on the new FIX (plan 09.1-07 Task 2, 2026-10-15)

why a new root (D-16, planner decision): the review fixes CR-01, WR-01, WR-02 and the troubleshooting correction moved
  FIX from 681c587 to the docs commit of plan 09.1-07 Task 1. The unchanged bench scripts write fixed folder names under
  PHASE8_EVIDENCE_ROOT, and those names in 09.1-evidence/ already hold the 681c587 run. The re-run therefore writes
  09.1-evidence/fix2/; the 681c587 evidence in the top-level folders of 09.1-evidence/ stays byte-identical as history.

scripts: not copied again. Every bench script the re-run uses (check-uat02.sh, check-uat04.sh, check-preflight.sh,
  preflight.sh, lib.sh, check-evidence-clean.sh, check-stale-anchor.sh, check-marker.sh, bench-users.sh, ha-test-guard,
  reseed-tombstones.sh) is cmp-identical to the 9.1 snapshot in 09.1-evidence/00-preflight/bench-scripts/, including the
  D-11 do_clean fix of check-uat02.sh, and ~/ha-test/phase9.1.env is unchanged against its snapshot. Proof:
  cmp-proof.txt.

new file: phase9.1-fix2.env, the copy of ~/ha-test/phase9.1-fix2.env (paths only, no secret, mode 0644). It exports
  PHASE8_EVIDENCE_ROOT=.../.planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-
  evidence/fix2 (honoured by evidence_root() in lib.sh), leaves PHASE8_EV_SUFFIX unset, and sets RESEED_EV_DIR=uat-04
  and RESEED_BACKUP_POINTER=$HOME/ha-test/.current-backup-phase9.1-fix2. ~/ha-test/phase9.1.env stays as snapshotted.
  Call form: bash -c '. ~/ha-test/phase9.1-fix2.env && ~/ha-test/bin/<script> <args>' from the repository root.

folders of the re-run (under 09.1-evidence/fix2/):
  00-preflight/      D-16's preflight/ folder, under the fixed name the unchanged scripts use.
  heal-start/        the StartedAt record at the moment FIX moved (bench-before-fix2.txt) and the heal start.
  uat-02/            run (a), the integration start (tombstones disabled_by integration); PHASE8_EV_SUFFIX unset.
  uat-02-null/       run (b), the null start (tombstones disabled_by null); PHASE8_EV_SUFFIX=-null for that run only.
  uat-04/            UAT-04 and the prepare.txt of reseed-tombstones.sh (RESEED_EV_DIR=uat-04).
  release/           push readiness of the new FIX (push-readiness.txt).
  cr01-observation/  later: the CR-01 observation.

never copied, on purpose: ~/ha-test/.mqtt-uat.env (the env file with the broker passwords), ~/ha-test/.token-*, every
  .storage directory, every backup directory (~/ha-test/_backup-*), the instance directories and the broker directory.

scan: ~/ha-test/bin/check-evidence-clean.sh over 09.1-evidence/fix2 prints PASS before the commit.
