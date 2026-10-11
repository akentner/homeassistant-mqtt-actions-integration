#!/usr/bin/env bash
# Marker fixture gate (Phase 8, plan 08-03).
#   check-marker.sh pending    entity on ha-a, mirror on ha-b, a pending approval issue on ha-b, no marker line in either log
#   check-marker.sh approved   same entities, NO pending approval issue on ha-b, the mirror available (not unavailable)
# `approved` does not require an empty log: it is called after UAT-03 counted marker lines.
# Run from inside the checkout (fixture ids come from ~/ha-test/.fixtures.env). Exit 0 PASS, 1 FAIL.
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"
G="$here/ha-test-guard"
mode=${1:-}
[ "$mode" = pending ] || [ "$mode" = approved ] || {
  echo "usage: check-marker.sh pending|approved" >&2
  exit 2
}

MARKER_ID=$(sed -n 's/^MARKER_ID=//p' "$HT/.fixtures.env" 2>/dev/null | head -n1)
[ -n "$MARKER_ID" ] || {
  echo "FAIL no MARKER_ID in ~/ha-test/.fixtures.env"
  exit 1
}

st() { # st LETTER -> "entity_id state" of the UAT Marker switch
  "$G" "$1" ws raw get_states |
    jq -r '[.result[] | select(.attributes.friendly_name=="UAT Marker") | "\(.entity_id) \(.state)"][0] // empty'
}
pending_issue() { # prints 1 when the approval issue for the marker is listed on ha-b
  "$G" b ws raw repairs/list_issues |
    jq -r --arg id "approval_$MARKER_ID" '[.result.issues[] | select(.domain=="mqtt_actions" and .issue_id==$id)] | length'
}

a=$(st a)
b=$(st b)
[ -n "$a" ] || chk_fail "no UAT Marker entity on ha-a"
[ -n "$b" ] || chk_fail "no UAT Marker mirror on ha-b"
n=$(pending_issue)
if [ "$mode" = pending ]; then
  [ "$n" = 1 ] || chk_fail "no pending approval issue for the marker on ha-b (found ${n:-none})"
  for l in a b; do
    c=$(grep -c "UAT03-MARKER" "$HT/$l/home-assistant.log" 2>/dev/null)
    [ "${c:-0}" -eq 0 ] || chk_fail "$c marker line(s) already in the log of ha-$l"
  done
else
  [ "$n" = 0 ] || chk_fail "the approval issue is still pending on ha-b"
  [ "${b##* }" != unavailable ] || chk_fail "the mirror on ha-b is unavailable"
  case "${a##* }" in unavailable) chk_fail "the marker on ha-a is unavailable" ;; esac
fi
chk_finish "check-marker $mode" "(a: ${a:-none}; b: ${b:-none})"
