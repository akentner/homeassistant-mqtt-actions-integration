#!/usr/bin/env bash
# P1-5 (Phase 1 item 5): the retained-versus-live chain with a real core MQTT client and a real retaining broker. Replayed state
# runs no action, a live change afterwards runs the actions once per instance. Phase 8, plan 08-03.
#   check-p15.sh run     toggle, full restart of ha-a and ha-b, reload of the core MQTT entry, positive control
# Run from inside the checkout that holds the evidence. Exit: 0 PASS, 1 FAIL, 2 ABORT (bench problem, never a result).
#
# EXPECTED VALUES ARE CODED HERE, BEFORE ANYTHING IS OBSERVED (D-08). The counted text is the marker line of the "UAT Marker"
# device ("UAT03-MARKER on" / "UAT03-MARKER off", both counted as one number) per instance log. HA rotates its log at every
# start, so the counts of the restarted lifetime stand alone and the old lifetime is copied into the evidence first.
#   precondition  the retained config document of the marker has run_on_startup false (else the check is void)
#   1  toggle           flip the marker state on ha-a (turn_off if on, else turn_on), wait 60 s:          marker lines +1 on ha-a, +1 on ha-b
#   2  full restart     podman restart ha-a ha-b, http up, 90 s:     marker lines in the NEW lifetime == 0 on both
#   3  broker reconnect reload of the core `mqtt` config entry on each instance, wait 60 s: marker lines still == 0 on both
#   4  positive control flip it back on ha-a, wait 60 s:           marker lines +1 on ha-a, +1 on ha-b
# mosq is never restarted (persistence off); its StartedAt must be unchanged at the end.
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"
G="$here/ha-test-guard"

[ "${1:-}" = run ] || {
  echo "usage: check-p15.sh run" >&2
  exit 2
}

EV="$(evidence_root)/p1-5${PHASE8_EV_SUFFIX:-}"
mkdir -p "$EV"
MARKER_ID=$(sed -n 's/^MARKER_ID=//p' "$HT/.fixtures.env" 2>/dev/null | head -n1)
CONFIG_TOPIC="mqtt_actions/v1/devices/${MARKER_ID}/config"
PAT="UAT03-MARKER"
ENT=switch.uat_marker

abort() {
  echo "ABORT $1" >&2
  verdict "$EV" ABORT "$1"
  exit 2
}
[ -n "$MARKER_ID" ] || abort "no MARKER_ID in .fixtures.env"
"$here/check-marker.sh" approved >/dev/null || abort "check-marker.sh approved does not print PASS"
"$here/check-preflight.sh" --quick >/dev/null || abort "check-preflight.sh --quick does not print PASS"

started() { podman inspect "$1" --format '{{.State.StartedAt}}' | sed -e 's/ m=.*//'; }
SA_MOSQ=$(started mosq)
SA_A0=$(started ha-a)
SA_B0=$(started ha-b)
cnt() { local n; n=$(grep -c -F -- "$PAT" "$HT/$1/home-assistant.log" 2>/dev/null); echo "${n:-0}"; }
delta() { echo $(($1 - $2)); }

RES=()
res() { RES+=("$1 $2 :: $3"); }
expect() { # expect LABEL OBSERVED EXPECTED
  if [ "$2" -eq "$3" ]; then res PASS "$1" "observed $2 (expected $3)"; else res FAIL "$1" "observed $2, expected $3"; fi
}
COUNTS="$EV/counts.txt"
: >"$COUNTS"
rec() { echo "$*" >>"$COUNTS"; }
: >"$EV/log-a.txt"
: >"$EV/log-b.txt"
save_logs() { # save_logs LABEL
  for l in a b; do
    {
      echo "== $1 (process lifetime of ha-$l: StartedAt $(started "ha-$l"))"
      grep -F -- "$PAT" "$HT/$l/home-assistant.log"
      echo "== end ($(cnt $l) marker line(s))"
    } >>"$EV/log-$l.txt"
  done
}

# ---- precondition: the startup flag of the marker is off ------------------------------------------------------------------
doc=$(probe_sub -t "$CONFIG_TOPIC" -C 1 -W 5)
flag=$(jq -r '[.. | objects | .run_on_startup? | select(. != null)] | first | if . == null then "missing" else tostring end' <<<"$doc" 2>/dev/null)
echo "retained config document of the marker: run_on_startup=$flag" >"$EV/mqtt-reload.txt"
[ "$flag" = false ] || abort "run_on_startup of the marker is '$flag', the check needs false"
res PASS "precondition run_on_startup" "false in the retained config document"

# ---- 1: toggle -----------------------------------------------------------------------------------------------------------------
a0=$(cnt a)
b0=$(cnt b)
# the toggle flips the current state (a service call to the state it already has is no edge); step 4 flips it back
cur=$("$G" a ws raw get_states | jq -r --arg e "$ENT" '[.result[] | select(.entity_id==$e) | .state][0] // "missing"')
case "$cur" in
  on) SVC1=switch.turn_off SVC4=switch.turn_on ;;
  off) SVC1=switch.turn_on SVC4=switch.turn_off ;;
  *) abort "the marker state on ha-a is '$cur', expected on or off" ;;
esac
"$G" a ws call "$SVC1" "{\"entity_id\":\"$ENT\"}" >/dev/null || abort "$SVC1 on ha-a failed"
sleep 60
a1=$(cnt a)
b1=$(cnt b)
rec "step 1 toggle ($SVC1 on ha-a, state before: $cur): ha-a $a0 -> $a1, ha-b $b0 -> $b1"
expect "1 toggle ha-a" "$(delta "$a1" "$a0")" 1
expect "1 toggle ha-b" "$(delta "$b1" "$b0")" 1
save_logs "lifetime 1, after the toggle"

# ---- 2: full restart of both containers ------------------------------------------------------------------------------------
podman restart -t 60 ha-a ha-b >/dev/null 2>&1 || abort "podman restart failed"
wait_http 8123 && wait_http 8124 || abort "an instance did not come up after the restart"
sleep 90
SA_A1=$(started ha-a)
SA_B1=$(started ha-b)
[ "$SA_A1" != "$SA_A0" ] && [ "$SA_B1" != "$SA_B0" ] || abort "StartedAt did not change, the restart did not happen"
a2=$(cnt a)
b2=$(cnt b)
rec "step 2 full restart (podman restart ha-a ha-b), NEW lifetime counts: ha-a $a2, ha-b $b2 (StartedAt ha-a $SA_A1, ha-b $SA_B1)"
expect "2 restart ha-a (new lifetime)" "$a2" 0
expect "2 restart ha-b (new lifetime)" "$b2" 0
save_logs "lifetime 2, 90 s after the restart"

# ---- 3: broker reconnect = reload of the core mqtt config entry ----------------------------------------------------------------
for l in a b; do
  entry=$("$G" "$l" ws raw config_entries/get '{"domain":"mqtt"}' | jq -r '[.result[] | select(.domain=="mqtt") | .entry_id][0] // empty')
  [ -n "$entry" ] || abort "no core mqtt config entry on ha-$l"
  out=$("$G" "$l" rest POST "/api/config/config_entries/entry/$entry/reload")
  echo "ha-$l: POST /api/config/config_entries/entry/<mqtt entry id $entry>/reload -> $out" >>"$EV/mqtt-reload.txt"
  jq -e 'has("require_restart")' <<<"$out" >/dev/null 2>&1 || abort "the mqtt entry reload on ha-$l gave no usable response"
done
sleep 60
a3=$(cnt a)
b3=$(cnt b)
rec "step 3 core mqtt entry reload on both, counts after 60 s (same lifetime as step 2): ha-a $a3, ha-b $b3"
expect "3 reconnect ha-a" "$a3" 0
expect "3 reconnect ha-b" "$b3" 0
[ "$(started ha-a)" = "$SA_A1" ] && [ "$(started ha-b)" = "$SA_B1" ] || res FAIL "3 same lifetime" "an instance restarted after step 2"
save_logs "lifetime 2, 60 s after the mqtt entry reload"

# ---- 4: positive control --------------------------------------------------------------------------------------------------------
"$G" a ws call "$SVC4" "{\"entity_id\":\"$ENT\"}" >/dev/null || abort "$SVC4 on ha-a failed"
sleep 60
a4=$(cnt a)
b4=$(cnt b)
rec "step 4 positive control ($SVC4 on ha-a): ha-a $a3 -> $a4, ha-b $b3 -> $b4"
expect "4 positive control ha-a" "$(delta "$a4" "$a3")" 1
expect "4 positive control ha-b" "$(delta "$b4" "$b3")" 1
save_logs "lifetime 2, after the positive control"

# ---- broker untouched, result ---------------------------------------------------------------------------------------------------
if [ "$(started mosq)" = "$SA_MOSQ" ]; then
  res PASS "mosq not restarted" "StartedAt $SA_MOSQ unchanged"
else
  res FAIL "mosq not restarted" "StartedAt changed from $SA_MOSQ to $(started mosq)"
fi
{
  for l in "${RES[@]}"; do echo "$l"; done
  echo "mosq StartedAt: $SA_MOSQ (unchanged when the line above says PASS)"
} >"$EV/result.txt"
cat "$EV/result.txt"

fails=$(grep -c '^FAIL ' "$EV/result.txt")
if [ "$fails" -eq 0 ]; then
  verdict "$EV" PASS "toggle +1, restart 0, mqtt entry reload 0, positive control +1, on both instances (see result.txt and counts.txt)"
  echo "PASS P1-5 $EV"
  exit 0
fi
verdict "$EV" FAIL "$(grep '^FAIL ' "$EV/result.txt" | tr '\n' ';')"
echo "FAIL P1-5 ($fails failed expectation(s))"
exit 1
