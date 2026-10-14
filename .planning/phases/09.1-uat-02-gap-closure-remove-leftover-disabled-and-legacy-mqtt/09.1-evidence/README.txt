Phase 9.1 evidence (folder map, D-16)

Every bench check in this tree ran on build FIX 681c58793b656b51869906b62f2564829de7a10d
(00-preflight/build.txt, sha: line). The bench scripts and the env file that ran them are in
00-preflight/bench-scripts/ (scrubbed copies; cmp-proof.txt proves them against ~/ha-test/bin/).
The scripts read this root through PHASE8_EVIDENCE_ROOT in ~/ha-test/phase9.1.env.

00-preflight/   D-16's preflight/ (the unchanged scripts write this fixed name). Pin of the bench to exactly FIX:
                build.txt, mount-hashes.txt, heartbeats.txt, retained-snapshot.txt, registry baselines, acl copy,
                backup manifest (written by preflight.sh), plus backup-phase9.1.txt (D-08 registry backup),
                bench-recovery.txt (mosq start after the host crash, red gate), pin-window.txt (HEAD detached at FIX
                for stage1 and stage2 only, D-13) and gate-pin.txt (red gate, then check-preflight.sh full and
                check-stale-anchor.sh PASS).
heal-start/     D-09 heal start: the first start of the fix build (preflight stage2) on the real leftover state.
                bench-before-fix.txt (plan 09.1-01), pre-state.txt, retained-before.txt, retained-after.txt,
                log-a.txt, log-b.txt, post-state-a.json, post-state-b.json, verdict.txt.
uat-02/         UAT-02 from integration tombstones (run a, user decision 1). This is the folder that
                reseed-tombstones.sh and check-uat04.sh read (baseline-a.json, baseline-b.json).
                prepare.txt holds the read-only start-state projection (--check, "would flip" lines).
uat-02-null/    UAT-02 from null tombstones (run b, PHASE8_EV_SUFFIX=-null). prepare.txt holds the restoration
                record and the regression-state line (its fixed wording "before UAT-04" is the script's).
uat-04/         UAT-04 (X1 to X10) from the restored null-tombstone state (D-12), with the guard, post-run and
                post-restart observations.
release/        push readiness, the owner's push of FIX, and CI and Validate on exactly FIX (plans 09.1-03, 09.1-04).

Observations (never expectations): neither UAT-02 run logged "Takeover of device ... postponed" (research
Pitfall 8) or "keeps its MQTT device", so no observations.txt was written in uat-02/ or uat-02-null/.
