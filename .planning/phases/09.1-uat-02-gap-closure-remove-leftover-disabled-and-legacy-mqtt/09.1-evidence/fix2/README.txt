Phase 9.1 evidence, second bench run on the new fix commit (folder map, D-16)

Every bench check in this tree ran on build FIX dc6513c0b4ac54d68fbf5207161508c18cc2a5b6
(00-preflight/build.txt, sha: line; release/push-readiness.txt, fix_sha: line). The bench scripts and the
env file that ran them are in 00-preflight/bench-scripts/ (scrubbed copies; cmp-proof.txt proves them
unchanged against ~/ha-test/bin/). The scripts read this root through PHASE8_EVIDENCE_ROOT in
~/ha-test/phase9.1-fix2.env.

The top-level folders of 09.1-evidence/ (00-preflight/, heal-start/, uat-02/, uat-02-null/, uat-04/,
release/) hold the superseded run on 681c58793b656b51869906b62f2564829de7a10d. They stay unchanged as history.

00-preflight/   D-16's preflight/ (the unchanged scripts write this fixed name). Pin of the bench to exactly FIX
                (plan 09.1-09): build.txt, mount-hashes.txt, heartbeats.txt, retained-snapshot.txt, registry
                baselines, acl copy, backup manifest, backup-phase9.1-fix2.txt, pin-window.txt and gate-pin.txt
                (red gate, then check-preflight.sh full and check-stale-anchor.sh PASS). The bench scripts are
                proven unchanged in bench-scripts/cmp-proof.txt. handoff.txt (plan 09.1-09) and
                uat-02/pin-reassert.txt (plan 09.1-10) link plans 09.1-09 and 09.1-10 as one pinned session.
heal-start/     D-09 heal start: the first start of FIX on the pre-state restored per owner decision 2
                (bench-before-fix2.txt, restore.txt, pre-state.txt, retained-before.txt, retained-after.txt, log-a.txt, log-b.txt,
                post-state-a.json, post-state-b.json, verdict.txt).
uat-02/         UAT-02 from integration tombstones (run a, user decision 1). This is the folder that
                reseed-tombstones.sh and check-uat04.sh read (baseline-a.json, baseline-b.json).
                pin-reassert.txt holds the re-assert of the pin before the first run; prepare.txt holds the
                read-only start-state projection (--check, "would flip" lines); observations.txt the log counts.
uat-02-null/    UAT-02 from null tombstones (run b, PHASE8_EV_SUFFIX=-null). prepare.txt holds the restoration
                record and the regression-state line (its fixed wording "before UAT-04" is the script's);
                observations.txt the log counts.
uat-04/         UAT-04 (X1 to X10) from the restored null-tombstone state (D-12), with the guard, post-run and
                post-restart observations.
release/        push readiness, the owner's push of FIX, and CI and Validate on exactly FIX (plans 09.1-07, 09.1-08).

Observations (never expectations): neither UAT-02 run logged "Takeover of device ... postponed" (research
Pitfall 8), "keeps its MQTT device" or the catch's final-pass "the next start checks again" line; see
observations.txt in uat-02/ and uat-02-null/.

cr01-observation/  Plan 09.1-11: one bench observation of the CR-01 case on FIX (observation only, never a UAT
                result; no verdict above changed). A renamed, enabled legacy test button next to an
                integration-disabled switch twin, with the legacy discovery still retained, across one start of
                ha-a and ha-b. Outcome: contradicts (outcome.txt, findings.txt): ha-b's takeover moved its renamed
                row to the native platform, its catch then removed the disabled switch twin on LEGACY content, and
                the clear core published deleted ha-a's kept, renamed button and emptied the topic. The bench was
                returned to the clean state with the fallback restore of the pre-observation registry copy
                (cleanup.txt, bench-notes.txt): check-uat02.sh clean, check-uat04.sh clean and
                check-preflight.sh --quick PASS, nothing retained, no record named "CR-01 kept button".
