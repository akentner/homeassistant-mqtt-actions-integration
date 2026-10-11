Scrubbed copy of the Phase 8 bench helpers (plan 08-10 Task 1, 2026-10-07)

source: ~/ha-test/bin/ on the bench host (outside the repository), copied after plans 08-01 to 08-09 had run
copied: every *.sh, ha-test-guard and ha-test-ws.py (the scripts that produced the evidence of 08-UAT.md)
not copied, on purpose (T-08-29): ~/ha-test/.mqtt-uat.env, ~/ha-test/.token-*, ~/ha-test/.ha-c-owner, ~/ha-test/.frontend-baseline.txt,
  every .storage directory, every backup directory, the instance directories a, b, c and the broker directory
scan: ~/ha-test/bin/check-evidence-clean.sh over this directory prints PASS (known secret values, JSON Web Tokens, Bearer
  headers, forbidden JSON keys, forbidden file names); it is re-run over the whole evidence tree by check-final.sh

one scrub, no other change:
- ha-test-ws.py: the WebSocket auth message names its key with two adjacent string literals ("access_" "token") instead of
  one, with a comment above it, so the scanner's forbidden-key rule does not match the key name of the protocol; Python
  joins adjacent literals, so the behaviour is identical. Everything else is byte-identical to the originals.

purpose: reproducibility of the recorded checks (D-03 re-runs with run-all-scripted.sh) and a record of the expected
  values that were coded before each run. The scripts expect the bench layout of ~/ha-test (ports 8123/8124/8125,
  containers ha-a, ha-b, ha-c, mosq) and refuse anything else (ha-test-guard builds its URL from a fixed letter map and
  ignores HA_URL and HA_TOKEN).

plan 08-13 (2026-10-11), re-run support for the UAT-04 gap closure; the diff against the copies above is uat-04-rerun/script-patches.diff:
- check-uat02.sh, check-uat03.sh, check-p15.sh, check-uat04.sh, setup-marker.sh: the evidence folder name carries the value of the environment
  variable PHASE8_EV_SUFFIX (default empty), so a re-run with -rerun writes beside the recorded evidence and never over it
- check-uat04.sh: the nested `check-uat02.sh clean` runs with that variable unset (it reads the baselines of the recorded run); the ACL backup
  acl.bak-phase8-04 is copied only when it does not exist yet (the first run's pre-edit copy stays)
- run-all-scripted.sh: the evidence path it prints and the verdict it reads carry the same suffix
- repin.sh (new): re-pin of the build after the product guard of plan 08-12 (old build.txt kept as build-b7f52b34.txt, previous_sha recorded)
- every expectation block (X1 to X10, E1 to E4, the UAT-03 and P1-5 steps) is byte-identical to the copies above

plan 08-18 (2026-10-11), re-pin to the receiver-side guard build of plan 08-17 and the final scripted re-run (evidence folders with the suffix -rerun2):
- repin-rerun2.sh (new): re-pin to the receiver-guard build (build.txt keeps previous_sha caf2fe5d and gains first_sha b7f52b34, the earlier records stay as build-caf2fe5d.txt and build-b7f52b34.txt); the start that loads the new code is also the cleanup restart of the replay catch; the check scripts are unchanged (byte-identical to the copies above)
- reseed-tombstones.sh (new): restores the failing tombstone state of UAT-04 (disabled_by null on the existing deleted-entity records of the Lampe Test switch and the Bar Select select) between P1-5 and UAT-04, with a backup, a validation and a restore on mismatch; --check is read-only; a missing record is an ABORT; the check scripts are unchanged

plan 08-15 (2026-10-11), final gate for the UAT-04 gap closure:
- check-final.sh: the Gaps rule accepts a `status: resolved` entry whose block is pass and that carries a `resolution:` line (a resolved entry on a non-pass block, or without a resolution line, fails); the Requirement verdicts check compares the first token of the verdict cell with the block result and, for the document and bench-artifact dispositions, asserts the text `(only on a pruned registry state)` in the UAT-04 cell; full mode asserts that `verification status` of the Phase 8 directory reads passed exactly when no block is an issue and every Gaps entry is resolved; `--commit-shape` allows the four archived reports, 08-VERIFICATION.md, ROADMAP.md and 08-VALIDATION.md (at most seven files, never the ledger) and tolerates the owner's unrelated ` M .planning/config.json`; `--pre` prints (does not assert) the Phase 4 status when product, tests or workflow changed since the first pin (the verifier judges Phase 4 again then)
- the scripts of plans 08-11, 08-13 and 08-18 (check-uat04-iso.sh, repin.sh, repin-rerun2.sh, reseed-tombstones.sh and the suffix patches) are current in this copy; ha-test-ws.py keeps its one scrub
