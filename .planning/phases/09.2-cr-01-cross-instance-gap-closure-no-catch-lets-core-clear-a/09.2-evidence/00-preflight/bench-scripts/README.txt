Bench environment of the Phase 9.2 re-run on FIX (plan 09.2-04 Task 2, 2026-10-15)

why a new root (D-14, D-17): Phase 9.2 moved FIX from dc6513c to 3dc9093f3cc49900bf76576cb4432d84aa94cd74 (the
  cross-instance CR-01 fix of plans 09.2-01 to 09.2-03 plus the owner-approved review fixes). The unchanged bench
  scripts write fixed folder names under PHASE8_EVIDENCE_ROOT, and those names in 09.1-evidence/ and 09.1-evidence/fix2/
  already hold the 681c587 and dc6513c runs. The 09.2 re-run therefore writes 09.2-evidence/; the 09.1 evidence, fix2/
  included, stays byte-identical as history and is never written again.

scripts: not copied again. Every bench script the re-run uses (check-uat02.sh, check-uat04.sh, check-preflight.sh,
  preflight.sh, lib.sh, check-evidence-clean.sh, check-stale-anchor.sh, check-marker.sh, bench-users.sh, ha-test-guard,
  reseed-tombstones.sh) is byte-identical to the 9.1 snapshot in
  .planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-evidence/00-preflight/bench-scripts/,
  including the D-11 do_clean fix of check-uat02.sh. ~/ha-test/phase9.1.env and ~/ha-test/phase9.1-fix2.env are
  unchanged. Proof: cmp-proof.txt.

new file: phase9.2.env, the copy of ~/ha-test/phase9.2.env (paths only, no secret, mode 0644). It exports
  PHASE8_EVIDENCE_ROOT=.../.planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-evidence
  (honoured by evidence_root() in lib.sh), leaves PHASE8_EV_SUFFIX unset, and sets RESEED_EV_DIR=uat-04 and
  RESEED_BACKUP_POINTER=$HOME/ha-test/.current-backup-phase9.2.
  Call form: bash -c '. ~/ha-test/phase9.2.env && ~/ha-test/bin/<script> <args>' from the repository root.

folders of the re-run (under 09.2-evidence/):
  00-preflight/  D-17's preflight folder, under the fixed name the unchanged scripts use.
  heal-start/    the StartedAt record at the moment FIX moved (bench-before.txt) and the heal start.
  uat-02/        D-17's uat-02-integration: run (a), the integration start (tombstones disabled_by integration);
                 PHASE8_EV_SUFFIX unset. reseed-tombstones.sh and check-uat04.sh read this folder.
  uat-02-null/   run (b), the null start (tombstones disabled_by null); PHASE8_EV_SUFFIX=-null for that run only.
  uat-04/        UAT-04 and the prepare.txt of reseed-tombstones.sh (RESEED_EV_DIR=uat-04).
  cr01-gate/     the CR-01 release gate, one folder per variant.
  release/       review decision, fast-forward record and push readiness of FIX.

never copied, on purpose: ~/ha-test/.mqtt-uat.env (the env file with the broker passwords), ~/ha-test/.token-*, every
  .storage directory, every backup directory (~/ha-test/_backup-*), the instance directories and the broker directory.

scan: ~/ha-test/bin/check-evidence-clean.sh over 09.2-evidence prints PASS before the commit.
