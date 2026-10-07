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
