#!/usr/bin/env bash
# Re-run entry for the scripted group of Phase 8 (UAT-02, UAT-03, P1-5, UAT-04). Written by plan 08-04 for D-03.
#
# A code change after the recorded build SHA (see `check-stale-anchor.sh`) makes the affected checks stale; re-run them with
# this script. The script records NOTHING itself: it never edits 08-UAT.md. A re-run is recorded by hand like the first run
# (block, table row, evidence folder, `check-recorded.sh ID`).
#
#   run-all-scripted.sh --list       print the order
#   run-all-scripted.sh --dry-run    print every command with the quick preflight that precedes it
#   run-all-scripted.sh              run them in that order, each after `check-preflight.sh --quick`; stops on ABORT (exit 2);
#                                    prints every verdict and the evidence path
#
# Preconditions that stay with the operator: the "UAT Marker" fixture (setup-marker.sh) must be in the state UAT-03 expects
# (`check-marker.sh pending`); a re-run of UAT-03 after approval needs a fresh marker. UAT-02 starts from a clean bench
# (`check-uat02.sh clean`), UAT-04 needs nothing retained under mqtt_actions_export/ or homeassistant/device/.
# Exit: 0 all PASS, 1 at least one FAIL, 2 ABORT (bench problem, nothing after it ran).
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"

# id|command|evidence folder|note
CHECKS=(
  "UAT-02|check-uat02.sh run|uat-02|two startup rounds with legacy Discovery published while stopped"
  "UAT-03|check-uat03.sh run|uat-03|needs the marker fixture (check-marker.sh pending)"
  "P1-5|check-p15.sh run|p1-5|toggle, full restart, MQTT entry reload, positive control"
  "UAT-04|check-uat04.sh run|uat-04|export on, export on the core prefix, export off"
)
GATE="check-preflight.sh --quick"

case "${1:-}" in
  --list)
    for c in "${CHECKS[@]}"; do
      IFS='|' read -r id cmd ev note <<<"$c"
      echo "$id  $cmd  ($note)"
    done
    exit 0
    ;;
  --dry-run)
    for c in "${CHECKS[@]}"; do
      IFS='|' read -r id cmd ev note <<<"$c"
      echo "$id: $BIN/$GATE && $BIN/$cmd   # evidence: $(evidence_root)/$ev"
      [ -x "$BIN/${cmd%% *}" ] || {
        echo "ABORT $BIN/${cmd%% *} is missing or not executable" >&2
        exit 2
      }
    done
    [ -x "$BIN/${GATE%% *}" ] || {
      echo "ABORT $BIN/${GATE%% *} is missing or not executable" >&2
      exit 2
    }
    exit 0
    ;;
  "") ;;
  *)
    echo "usage: run-all-scripted.sh [--list | --dry-run]" >&2
    exit 2
    ;;
esac

worst=0
for c in "${CHECKS[@]}"; do
  IFS='|' read -r id cmd ev note <<<"$c"
  echo "== $id: quick gate"
  # shellcheck disable=SC2086
  "$BIN/${GATE%% *}" --quick || {
    echo "ABORT $id: the quick preflight gate does not print PASS"
    exit 2
  }
  echo "== $id: $cmd"
  # shellcheck disable=SC2086
  "$BIN/${cmd%% *}" ${cmd#* }
  rc=$?
  verdict_line=$(head -n1 "$(evidence_root)/$ev/verdict.txt" 2>/dev/null || echo "no verdict.txt")
  echo "== $id: exit $rc, verdict: $verdict_line, evidence: $(evidence_root)/$ev"
  case "$rc" in
    0) ;;
    2)
      echo "ABORT $id: bench problem, nothing after it was run"
      exit 2
      ;;
    *) worst=1 ;;
  esac
done
exit $worst
