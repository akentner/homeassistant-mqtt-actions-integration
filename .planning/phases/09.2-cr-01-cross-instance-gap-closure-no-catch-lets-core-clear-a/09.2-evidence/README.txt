Phase 9.2 evidence, bench re-run on the fix commit (folder map, D-17)

Every bench check in this tree ran on build FIX 3dc9093f3cc49900bf76576cb4432d84aa94cd74
(00-preflight/build.txt, sha: line; release/push-readiness.txt, fix_sha: line). The bench scripts and the env file
that ran them are in 00-preflight/bench-scripts/ (scrubbed copies; cmp-proof.txt proves them unchanged against
~/ha-test/bin/). The scripts read this root through PHASE8_EVIDENCE_ROOT in ~/ha-test/phase9.2.env.

The 09.1 evidence (09.1-evidence/ and 09.1-evidence/fix2/, builds 681c587 and dc6513c) is history and stays unchanged.

00-preflight/   D-17's preflight/ (the unchanged scripts write this fixed name). Pin of the bench to exactly FIX
                (plan 09.2-06): bench-decision.txt, backup-phase9.2.txt, build.txt, mount-hashes.txt, heartbeats.txt,
                retained-snapshot.txt, registry baselines, acl copy, backup manifest, pin-window.txt and gate-pin.txt
                (red gate, then check-preflight.sh full and check-stale-anchor.sh PASS). The bench scripts are proven
                unchanged in bench-scripts/cmp-proof.txt (plan 09.2-04). handoff.txt (plan 09.2-06) and
                uat-02/pin-reassert.txt (plan 09.2-07) link plans 09.2-06, 09.2-07 and 09.2-08 as one pinned session.
heal-start/     D-14 heal start: the first start of FIX on the pre-state restored per bench-decision.txt (choice
                confirm, heal_restore yes): bench-before.txt, restore.txt, pre-state.txt, retained-before.txt,
                retained-after.txt, log-a.txt, log-b.txt, post-state-a.json, post-state-b.json, verdict.txt.
uat-02/         D-17's uat-02-integration: UAT-02 from integration tombstones (run a). This is the folder that
                reseed-tombstones.sh and check-uat04.sh read (baseline-a.json, baseline-b.json).
                pin-reassert.txt holds the re-assert of the pin before the first run; prepare.txt holds the read-only
                start-state projection (--check, "would flip" lines); observations.txt the log counts.
uat-02-null/    UAT-02 from null tombstones (run b, PHASE8_EV_SUFFIX=-null). prepare.txt holds the restoration record
                and the regression-state line (its fixed wording "before UAT-04" is the script's); observations.txt the
                log counts.
uat-04/         UAT-04 (X1 to X10) from the restored null-tombstone state (09.1 D-12), with the guard, post-run and
                post-restart observations.
cr01-gate/      plan 09.2-08: the CR-01 release gate on FIX.
release/        review decision, push readiness, the fast-forward, the owner's push of FIX, and CI and Validate on
                exactly FIX (plans 09.2-04 and 09.2-05).

Observations (never expectations): neither UAT-02 run logged "Takeover of device ... postponed", "keeps its MQTT
device", any "Kept the MQTT entities of N native devices" line ("another instance keeps", "was not heard yet", "is not
known"), "cannot announce" or the catch's final-pass "the next start checks again" line; see observations.txt in
uat-02/ and uat-02-null/.
