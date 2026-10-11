#!/usr/bin/env bash
# UAT-03: a command on one of two real instances runs the actions exactly once on every approved instance; an unknown payload
# is ignored and leaves the state unchanged. Phase 8, plan 08-03.
#   check-uat03.sh run     steps A (unapproved control), approve, B, C, D; writes the evidence folder and verdict.txt
# Run from inside the checkout that holds the evidence. Exit: 0 PASS, 1 FAIL, 2 ABORT (bench problem, never a UAT result).
#
# EXPECTED VALUES ARE CODED HERE, BEFORE ANYTHING IS OBSERVED (D-08). Counting rule: per instance, the number of log lines with
# the exact marker text in ~/ha-test/{a,b}/home-assistant.log, before and after each step, inside ONE process lifetime (the log
# is rotated at every start). Only deltas are asserted. A step waits after its trigger, so "delta == 1" also rules out a late
# echo or replay run.
#   A  (unapproved control)  switch.turn_on on ha-a, wait 60 s:   "UAT03-MARKER on"  delta ha-a +1, ha-b 0
#      approve the mirror on ha-b (Repairs fix flow API)
#   B  (command on the owner) switch.turn_off on ha-a, wait 60 s: "UAT03-MARKER off" delta ha-a +1, ha-b +1
#   C  (command on a mirror)  switch.turn_on on ha-b, wait 60 s:  "UAT03-MARKER on"  delta ha-a +1, ha-b +1
#   D  (unknown payload)      `banana`, QoS 1, NOT retained, on the marker's state topic as uat_bridge, wait 30 s:
#                             on and off deltas 0 on both; "Ignoring unknown payload" delta +1 on both;
#                             entity state on both unchanged; the retained value on the broker unchanged;
#                             the topic capture shows the banana message with retain flag 0
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"
G="$here/ha-test-guard"

[ "${1:-}" = run ] || {
  echo "usage: check-uat03.sh run" >&2
  exit 2
}

EV="$(evidence_root)/uat-03${PHASE8_EV_SUFFIX:-}"
mkdir -p "$EV"
MARKER_ID=$(sed -n 's/^MARKER_ID=//p' "$HT/.fixtures.env" 2>/dev/null | head -n1)
TOPIC="mqtt_actions/v1/devices/${MARKER_ID}/state"
P_ON="UAT03-MARKER on"
P_OFF="UAT03-MARKER off"
P_UNK="Ignoring unknown payload"
ENT=switch.uat_marker
WAIT_CMD=60
WAIT_UNK=30

ABORT_MSG=""
abort() {
  echo "ABORT $1" >&2
  verdict "$EV" ABORT "$1"
  exit 2
}
probe_pid=""
trap '[ -n "$probe_pid" ] && kill "$probe_pid" 2>/dev/null' EXIT

[ -n "$MARKER_ID" ] || abort "no MARKER_ID in .fixtures.env"
"$here/check-marker.sh" pending >/dev/null || abort "check-marker.sh pending does not print PASS"
"$here/check-preflight.sh" --quick >/dev/null || abort "check-preflight.sh --quick does not print PASS"

started() { podman inspect "$1" --format '{{.State.StartedAt}}' | sed -e 's/ m=.*//'; }
SA_A=$(started ha-a)
SA_B=$(started ha-b)
SA_MOSQ=$(started mosq)

cnt() { # cnt LETTER PATTERN
  local n
  n=$(grep -c -F -- "$2" "$HT/$1/home-assistant.log" 2>/dev/null)
  echo "${n:-0}"
}
snap() { # snap -> "aon aoff aunk bon boff bunk"
  echo "$(cnt a "$P_ON") $(cnt a "$P_OFF") $(cnt a "$P_UNK") $(cnt b "$P_ON") $(cnt b "$P_OFF") $(cnt b "$P_UNK")"
}
estate() { "$G" "$1" ws raw get_states | jq -r --arg e "$ENT" '[.result[] | select(.entity_id==$e) | .state][0] // "missing"'; }
retained() { probe_sub -t "$TOPIC" -C 1 -W 5 -F '%r %p'; }

RES=()
res() { RES+=("$1 $2 :: $3"); }
COUNTS="$EV/counts.txt"
: >"$COUNTS"
step_counts() { # step_counts NAME "before" "after"
  {
    echo "step $1"
    echo "  columns: a_on a_off a_unknown b_on b_off b_unknown"
    echo "  before: $2"
    echo "  after:  $3"
  } >>"$COUNTS"
}
delta() { # delta "before" "after" INDEX(1-6)
  local b a
  b=$(awk -v i="$3" '{print $i}' <<<"$1")
  a=$(awk -v i="$3" '{print $i}' <<<"$2")
  echo $((a - b))
}
expect() { # expect STEP LABEL OBSERVED EXPECTED
  if [ "$3" -eq "$4" ]; then
    res PASS "$1 $2" "delta $3 (expected $4)"
  else
    res FAIL "$1 $2" "observed delta $3, expected $4"
  fi
}

# the capture of the whole run: topic, retain flag and payload with a timestamp
probe_sub -v -t "$TOPIC" -F '%I %t retain=%r payload=%p' >"$EV/topic-capture.txt" 2>&1 &
probe_pid=$!
sleep 2

# ---- A: unapproved control ---------------------------------------------------------------------------------------------
B0=$(snap)
"$G" a ws call switch.turn_on "{\"entity_id\":\"$ENT\"}" >/dev/null || abort "switch.turn_on on ha-a failed"
sleep "$WAIT_CMD"
A1=$(snap)
step_counts A "$B0" "$A1"
expect A "ha-a on" "$(delta "$B0" "$A1" 1)" 1
expect A "ha-b on (unapproved)" "$(delta "$B0" "$A1" 4)" 0

# ---- approve the mirror on ha-b through the Repairs fix flow API -------------------------------------------------------
ISSUE="approval_${MARKER_ID}"
fix=$("$G" b rest POST /api/repairs/issues/fix "{\"handler\":\"mqtt_actions\",\"issue_id\":\"$ISSUE\"}")
flow=$(jq -r '.flow_id // empty' <<<"$fix" 2>/dev/null)
[ -n "$flow" ] || abort "the Repairs fix flow did not start (response keys: $(jq -rc 'keys' <<<"$fix" 2>/dev/null))"
{
  echo "approval via Repairs fix flow API on ha-b"
  echo "start: type=$(jq -r '.type' <<<"$fix") step_id=$(jq -r '.step_id // "-"' <<<"$fix")"
} >"$EV/approval.txt"
sub=$("$G" b rest POST "/api/repairs/issues/fix/$flow" '{}')
echo "submit: type=$(jq -r '.type // "-"' <<<"$sub") reason=$(jq -r '.reason // "-"' <<<"$sub")" >>"$EV/approval.txt"
[ "$(jq -r '.type // empty' <<<"$sub")" = create_entry ] || abort "the approval flow did not end in create_entry"
sleep 5
"$here/check-marker.sh" approved >>"$EV/approval.txt" || abort "check-marker.sh approved does not print PASS after the approval"
res PASS "approve ha-b" "$(tail -n1 "$EV/approval.txt")"

# ---- B: command on the owner, approved ---------------------------------------------------------------------------------
B0=$(snap)
"$G" a ws call switch.turn_off "{\"entity_id\":\"$ENT\"}" >/dev/null || abort "switch.turn_off on ha-a failed"
sleep "$WAIT_CMD"
B1=$(snap)
step_counts B "$B0" "$B1"
expect B "ha-a off" "$(delta "$B0" "$B1" 2)" 1
expect B "ha-b off" "$(delta "$B0" "$B1" 5)" 1

# ---- C: command on the mirror --------------------------------------------------------------------------------------------
C0=$(snap)
"$G" b ws call switch.turn_on "{\"entity_id\":\"$ENT\"}" >/dev/null || abort "switch.turn_on on ha-b failed"
sleep "$WAIT_CMD"
C1=$(snap)
step_counts C "$C0" "$C1"
expect C "ha-a on" "$(delta "$C0" "$C1" 1)" 1
expect C "ha-b on" "$(delta "$C0" "$C1" 4)" 1

# ---- D: unknown payload ----------------------------------------------------------------------------------------------------
SB_A=$(estate a)
SB_B=$(estate b)
RET_BEFORE=$(retained)
jq -n --arg a "$SB_A" --arg b "$SB_B" --arg r "$RET_BEFORE" '{"ha-a": $a, "ha-b": $b, "retained_on_broker": $r}' >"$EV/states-before.json"
D0=$(snap)
bridge_pub -t "$TOPIC" -m banana -q 1 || abort "the uat_bridge publish of banana failed"
sleep "$WAIT_UNK"
D1=$(snap)
step_counts D "$D0" "$D1"
SA_A2=$(estate a)
SA_B2=$(estate b)
RET_AFTER=$(retained)
jq -n --arg a "$SA_A2" --arg b "$SA_B2" --arg r "$RET_AFTER" '{"ha-a": $a, "ha-b": $b, "retained_on_broker": $r}' >"$EV/states-after.json"
expect D "ha-a marker on" "$(delta "$D0" "$D1" 1)" 0
expect D "ha-a marker off" "$(delta "$D0" "$D1" 2)" 0
expect D "ha-b marker on" "$(delta "$D0" "$D1" 4)" 0
expect D "ha-b marker off" "$(delta "$D0" "$D1" 5)" 0
expect D "ha-a unknown-payload warning" "$(delta "$D0" "$D1" 3)" 1
expect D "ha-b unknown-payload warning" "$(delta "$D0" "$D1" 6)" 1
[ "$SB_A" = "$SA_A2" ] && res PASS "D ha-a state unchanged" "$SB_A" || res FAIL "D ha-a state unchanged" "before $SB_A after $SA_A2"
[ "$SB_B" = "$SA_B2" ] && res PASS "D ha-b state unchanged" "$SB_B" || res FAIL "D ha-b state unchanged" "before $SB_B after $SA_B2"
if [ -n "$RET_BEFORE" ] && [ "$RET_BEFORE" = "$RET_AFTER" ]; then
  res PASS "D retained value on the broker unchanged" "$RET_BEFORE"
else
  res FAIL "D retained value on the broker unchanged" "before '$RET_BEFORE' after '$RET_AFTER'"
fi
kill "$probe_pid" 2>/dev/null
probe_pid=""
sleep 1
if grep -q 'retain=0 payload=banana' "$EV/topic-capture.txt"; then
  res PASS "D banana was not retained" "capture shows retain=0"
else
  res FAIL "D banana was not retained" "no 'retain=0 payload=banana' line in topic-capture.txt"
fi

# ---- same process lifetime and untouched broker ----------------------------------------------------------------------------
[ "$(started ha-a)" = "$SA_A" ] && [ "$(started ha-b)" = "$SA_B" ] || res FAIL "process lifetime" "an instance restarted during the run, counts are void"
[ "$(started mosq)" = "$SA_MOSQ" ] || res FAIL "broker" "mosq restarted during the run"

# ---- evidence ------------------------------------------------------------------------------------------------------------------
grep -F -e "UAT03-MARKER" -e "$P_UNK" "$HT/a/home-assistant.log" >"$EV/log-a.txt"
grep -F -e "UAT03-MARKER" -e "$P_UNK" "$HT/b/home-assistant.log" >"$EV/log-b.txt"
{
  for l in "${RES[@]}"; do echo "$l"; done
  echo "containers: ha-a StartedAt=$SA_A ha-b StartedAt=$SA_B mosq StartedAt=$SA_MOSQ (unchanged during the run unless a FAIL line says so)"
} >"$EV/result.txt"
cat "$EV/result.txt"

fails=$(grep -c '^FAIL ' "$EV/result.txt")
if [ "$fails" -eq 0 ]; then
  verdict "$EV" PASS "steps A, B, C and D hold on both instances (see result.txt and counts.txt)"
  echo "PASS UAT-03 $EV"
  exit 0
fi
verdict "$EV" FAIL "$(grep '^FAIL ' "$EV/result.txt" | tr '\n' ';')"
echo "FAIL UAT-03 ($fails failed expectation(s))"
exit 1
