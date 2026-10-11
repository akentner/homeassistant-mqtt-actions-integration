#!/usr/bin/env bash
# Phase 8, plan 08-07: select flow (P2-1) and breaker loop (P2-2) on the real bench. Lives outside the repository.
#
#   check-p22.sh p21        headless pre-check of the select subentry flow on ha-a (same flow steps the frontend drives); leaves the
#                           device "UAT P2-1" with three options for the owner; writes p2-1/flow-precheck.txt
#   check-p22.sh setup      import "UAT Loop" with inert actions, reconfigure it to the loop through the subentry flow, read the
#                           retained config document and write p2-2/loop-config.txt (ABORT when it does not carry the loop)
#   check-p22.sh run        the breaker run (trip, pause, restart while paused, release, re-trip); writes the p2-2 evidence and
#                           verdict.txt (PASS / FAIL / ABORT as first token)
#   check-p22.sh teardown   release (hub entry reload), delete the throwaway devices of this plan, wait
#   check-p22.sh peek ID    keys of the retained config document of a device (structure only)
#
# Only ha-a is driven (ha-test-guard letter a); ha-b is only read. UAT Loop is never approved on ha-b (T-08-21).
# Run from inside a checkout (the evidence folder comes from the git toplevel). Exit: 0 PASS, 1 FAIL, 2 ABORT/usage.
#
# EXPECTED VALUES ARE CODED HERE, BEFORE ANYTHING IS OBSERVED (D-08).
#   P2-1 menus of the select flow (state in the draft -> menu entries, in this order):
#     0 options  add_option,settings
#     1 option   add_option,edit_option,settings
#     2 options  add_option,edit_option,settings,done                     Done offered, Remove hidden
#     3 options  add_option,edit_option,remove_option,settings,done       Remove offered
#     reconfigure of 3 options: add_option,edit_option,remove_option,settings,done,delete_device
#     after removing one of three: Remove hidden again (2 options)
#   P2-2 loop (breaker 5 runs per 10 s): live messages on the state topic after the external ON:
#     trip      5..8 live messages (expected 6: one external + five action publishes), issue circuit_breaker_{uuid} on ha-a within
#               15 s, exactly one "Circuit breaker tripped for device UAT Loop" warning since the run started
#     paused    external opposite value: exactly +1 live message within 10 s (no action ran)
#     restart   podman restart ha-a, wait_http, 90 s: issue still listed; external opposite value: exactly +1 live message
#     release   reload of the hub entry: the issue is gone within 20 s; external opposite value: 5..8 new live messages, the issue
#               exists again within 20 s (re-trip)
#     runaway   more than 50 live messages at any moment: delete the device, ABORT-like FAIL (T-08-19)
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"
G="$here/ha-test-guard"
FX="$HT/.fixtures-frontend.env"
EV=$(evidence_root)
E1="$EV/p2-1"
E2="$EV/p2-2"
LOOP_NAME="UAT Loop"
P21_NAME="UAT P2-1"

fx_get() { sed -n "s/^$1=//p" "$FX" 2>/dev/null | head -n1; }
fx_set() {
  touch "$FX"
  chmod 600 "$FX"
  grep -v "^$1=" "$FX" >"$FX.new" || true
  echo "$1=$2" >>"$FX.new"
  mv "$FX.new" "$FX"
}
entry_id() { "$G" a rest GET /api/config/config_entries/entry | jq -r '[.[] | select(.domain=="mqtt_actions")][0].entry_id'; }
subs() { # type, title, subentry_id, unique_id per line
  local eid
  eid=$(entry_id)
  "$G" a ws raw config_entries/subentries/list "{\"entry_id\":\"$eid\"}" |
    jq -r '.result[] | [.subentry_type, .title, .subentry_id, (.unique_id // "")] | @tsv'
}
sub_field() { # TITLE COLUMN(3=subentry id, 4=uuid)
  subs | awk -F'\t' -v t="$1" -v c="$2" '$2 == t {print $c; exit}'
}
issues() { "$G" a ws raw repairs/list_issues | jq -r '.result.issues[] | "\(.domain) \(.issue_id)"'; }
cfg_doc() { probe_sub -t "mqtt_actions/v1/devices/$1/config" -C 1 -W 5 -F '%p' 2>/dev/null; }

# ---- subentry flow over REST (the same steps the frontend drives) -----------------------------------------------------
EID=""
fstart() { # TYPE [SUBENTRY_ID]
  local body
  body=$(jq -nc --arg e "$EID" --arg t "$1" --arg s "${2:-}" '{handler:[$e,$t]} + (if $s != "" then {subentry_id:$s} else {} end)')
  "$G" a rest POST /api/config/config_entries/subentries/flow "$body"
}
fnext() { "$G" a rest POST "/api/config/config_entries/subentries/flow/$1" "$2"; }

TRACE=""
step() { # step LABEL RESPONSE : one trace line, no secrets possible in these responses
  printf '%s: %s\n' "$1" "$(jq -c '{type, step_id, menu_options, errors, reason, placeholders: .description_placeholders}' <<<"$2" 2>/dev/null || echo "$2" | head -c 300)" >>"$TRACE"
}
expect_menu() { # LABEL RESPONSE "a,b,c"
  local got
  got=$(jq -r 'if .type=="menu" then (.menu_options|join(",")) else "NOT-A-MENU:" + (.type // "?") + ":" + (.step_id // "") end' <<<"$2")
  step "$1" "$2"
  [ "$got" = "$3" ] || chk_fail "$1: menu is '$got', expected '$3'"
}
expect_form() { # LABEL RESPONSE STEP_ID
  step "$1" "$2"
  [ "$(jq -r '.type + ":" + (.step_id // "")' <<<"$2")" = "form:$3" ] || chk_fail "$1: expected form $3, got $(jq -c '{type,step_id,errors}' <<<"$2")"
}

# ---- P2-1 --------------------------------------------------------------------------------------------------------------------
do_p21() {
  mkdir -p "$E1"
  TRACE="$E1/flow-precheck.txt"
  EID=$(entry_id)
  [ -n "$EID" ] && [ "$EID" != null ] || {
    echo "ABORT no mqtt_actions entry on ha-a"
    return 2
  }
  if [ -n "$(sub_field "$P21_NAME" 3)" ]; then
    echo "ABORT $P21_NAME already exists on ha-a"
    return 2
  fi
  {
    echo "P2-1 headless pre-check of the select subentry flow on ha-a ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
    echo "Driven over the subentry flow REST API (the endpoints the frontend uses), build $(sed -n 's/^sha: //p' "$EV/00-preflight/build.txt" | head -n1)."
    echo "Rendering (labels, wording, layout) is NOT judged here; that is the owner's part. Only menu entries and data are asserted."
    echo
  } >"$TRACE"
  local r fid sid uuid
  r=$(fstart select)
  fid=$(jq -r '.flow_id' <<<"$r")
  expect_form "1 start (settings form)" "$r" user
  r=$(fnext "$fid" "$(jq -nc --arg n "$P21_NAME" '{name:$n, run_on_startup:false, run_mode:"serial", breaker_max_runs:5, breaker_window:10}')")
  expect_menu "2 settings submitted, 0 options" "$r" "add_option,settings"
  r=$(fnext "$fid" '{"next_step_id":"add_option"}')
  expect_form "3 add option form" "$r" add_option
  r=$(fnext "$fid" '{"state_value":"one","friendly_name":"One","actions":[]}')
  expect_menu "4 one option added" "$r" "add_option,edit_option,settings"
  r=$(fnext "$fid" '{"next_step_id":"add_option"}')
  r=$(fnext "$fid" '{"state_value":"two","friendly_name":"Two","actions":[]}')
  expect_menu "5 two options: Done offered, Remove hidden" "$r" "add_option,edit_option,settings,done"
  r=$(fnext "$fid" '{"next_step_id":"add_option"}')
  r=$(fnext "$fid" '{"state_value":"three","friendly_name":"Three","actions":[]}')
  expect_menu "6 three options: Remove offered" "$r" "add_option,edit_option,remove_option,settings,done"
  r=$(fnext "$fid" '{"next_step_id":"done"}')
  step "7 Done (create)" "$r"
  [ "$(jq -r '.type' <<<"$r")" = create_entry ] || chk_fail "7: Done did not create the device"
  sleep 8
  sid=$(sub_field "$P21_NAME" 3)
  uuid=$(sub_field "$P21_NAME" 4)
  [ -n "$sid" ] || chk_fail "7: subentry $P21_NAME not listed"
  [ -n "$uuid" ] && fx_set P21_ID "$uuid"

  if [ -n "$sid" ]; then
    # reconfigure: edit, remove, add
    r=$(fstart select "$sid")
    fid=$(jq -r '.flow_id' <<<"$r")
    expect_menu "8 reconfigure menu (3 options, delete offered)" "$r" "add_option,edit_option,remove_option,settings,done,delete_device"
    r=$(fnext "$fid" '{"next_step_id":"edit_option"}')
    expect_form "9 edit: choose option" "$r" edit_option
    r=$(fnext "$fid" '{"option":"one"}')
    expect_form "10 edit: details of One (state value locked)" "$r" edit_option_details
    r=$(fnext "$fid" '{"friendly_name":"One edited","actions":[]}')
    expect_menu "11 One renamed" "$r" "add_option,edit_option,remove_option,settings,done,delete_device"
    r=$(fnext "$fid" '{"next_step_id":"remove_option"}')
    expect_form "12 remove: choose option" "$r" remove_option
    r=$(fnext "$fid" '{"option":"two"}')
    step "13 remove: confirm Two" "$r"
    [ "$(jq -r '.type + ":" + (.step_id // "")' <<<"$r")" = "menu:remove_confirm" ] || chk_fail "13: expected the remove_confirm menu"
    r=$(fnext "$fid" '{"next_step_id":"remove_confirmed"}')
    expect_menu "14 Two removed (2 options): Remove hidden again" "$r" "add_option,edit_option,settings,done,delete_device"
    r=$(fnext "$fid" '{"next_step_id":"add_option"}')
    r=$(fnext "$fid" '{"state_value":"four","friendly_name":"Four","actions":[]}')
    expect_menu "15 Four added (3 options): Remove offered" "$r" "add_option,edit_option,remove_option,settings,done,delete_device"
    r=$(fnext "$fid" '{"next_step_id":"done"}')
    step "16 Done (reconfigure saved)" "$r"
    [ "$(jq -r '.type' <<<"$r")" = abort ] || chk_fail "16: reconfigure did not end"
    sleep 8
    {
      echo
      echo "retained config document after the reconfigure (options only):"
      cfg_doc "$uuid" | jq -c '[.. | objects | select(has("state_value")) | {state_value, friendly_name}]' 2>/dev/null || echo "  (document not readable)"
    } >>"$TRACE"
    [ "$(cfg_doc "$uuid" | jq -c '[.. | objects | select(has("state_value")) | .state_value]' 2>/dev/null)" = '["one","three","four"]' ] ||
      chk_fail "after the reconfigure the retained document does not hold the options one, three, four"
    cfg_doc "$uuid" | jq -e '[.. | objects | select(.friendly_name=="One edited")] | length >= 1' >/dev/null 2>&1 ||
      chk_fail "the renamed option One edited is not in the retained document"
  fi
  chk_finish "check-p22 p21 (flow pre-check)" "$TRACE" | tee -a "$TRACE"
}

# ---- P2-2 setup ---------------------------------------------------------------------------------------------------------------
do_setup() {
  mkdir -p "$E2"
  local f="$E2/loop-config.txt" eid uuid sid r fid inert topic loop_on loop_off doc
  EID=$(entry_id)
  [ -n "$(sub_field "$LOOP_NAME" 3)" ] && {
    echo "ABORT $LOOP_NAME already exists on ha-a"
    return 2
  }
  inert='[{"action":"system_log.write","data":{"message":"UAT loop inert","level":"info"}}]'
  doc=$(jq -nc --arg n "$LOOP_NAME" --argjson a "$inert" \
    '{data:{format:"mqtt_actions_export",export_version:1,devices:[{kind:"switch",name:$n,on_change_to_on:$a,on_change_to_off:$a,run_mode:"serial",run_on_startup:false,breaker_max_runs:5,breaker_window:10}]}}')
  "$G" a ws call mqtt_actions.import_devices "$doc" >/dev/null || {
    echo "ABORT import_devices failed"
    return 2
  }
  sleep 8
  uuid=$(sub_field "$LOOP_NAME" 4)
  sid=$(sub_field "$LOOP_NAME" 3)
  [ -n "$uuid" ] && [ -n "$sid" ] || {
    echo "ABORT $LOOP_NAME not listed after the import"
    return 2
  }
  fx_set LOOP_ID "$uuid"
  topic="mqtt_actions/v1/devices/$uuid/state"
  loop_on=$(jq -nc --arg t "$topic" '[{action:"mqtt.publish",data:{topic:$t,payload:"OFF",retain:false}}]')
  loop_off=$(jq -nc --arg t "$topic" '[{action:"mqtt.publish",data:{topic:$t,payload:"ON",retain:false}}]')
  r=$(fstart switch "$sid")
  fid=$(jq -r '.flow_id' <<<"$r")
  r=$(fnext "$fid" '{"next_step_id":"edit_device"}')
  [ "$(jq -r '.step_id' <<<"$r")" = edit_device ] || {
    echo "ABORT reconfigure flow did not reach edit_device"
    return 2
  }
  r=$(fnext "$fid" "$(jq -nc --arg n "$LOOP_NAME" --argjson on "$loop_on" --argjson off "$loop_off" \
    '{name:$n, on_change_to_on:$on, on_change_to_off:$off, run_on_startup:false, run_mode:"serial", breaker_max_runs:5, breaker_window:10}')")
  [ "$(jq -r '.type' <<<"$r")" = abort ] || {
    echo "ABORT reconfigure did not save: $(jq -c '{type,step_id,errors}' <<<"$r")"
    return 2
  }
  sleep 8
  {
    echo "P2-2 loop device configuration proof ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
    echo "device: $LOOP_NAME uuid: $uuid"
    echo "state topic: $topic"
    echo "set through the subentry reconfigure flow (step edit_device) over REST; the browser action editor was not used (no browser MCP)."
    echo
    echo "mqtt.publish actions found in the retained config document (action, topic, payload, retain):"
    cfg_doc "$uuid" | jq -c '[.. | objects | select(.action? == "mqtt.publish") | {action, topic: .data.topic, payload: .data.payload, retain: .data.retain}]'
    echo
    echo "trigger lists of the retained document (keys only):"
    cfg_doc "$uuid" | jq -c 'keys'
  } >"$f"
  cat "$f"
  if cfg_doc "$uuid" | jq -e --arg t "$topic" \
    '([.. | objects | select(.action? == "mqtt.publish" and .data.topic == $t and .data.payload == "OFF")] | length >= 1)
     and ([.. | objects | select(.action? == "mqtt.publish" and .data.topic == $t and .data.payload == "ON")] | length >= 1)' >/dev/null; then
    echo "PASS loop document carries both mqtt.publish actions with the device's own state topic" | tee -a "$f"
  else
    echo "ABORT loop document does not carry the loop" | tee -a "$f"
    return 2
  fi
  # the mirror on ha-b must never be approved (T-08-21): a loop with mqtt.publish is shown there as a blocked issue, not as an
  # approval request, because mqtt.publish is a denied service for actions that arrive from the broker
  sleep 10
  {
    echo
    echo "ha-b (never approved by this plan), issues naming the loop device:"
    "$G" b ws raw repairs/list_issues | jq -r --arg u "$uuid" '.result.issues[] | select(.issue_id | endswith($u)) | "  \(.domain) \(.issue_id)"'
    echo "(a blocked_{uuid} issue means mqtt.publish is denied for actions received from the broker: the loop cannot run on ha-b at all)"
  } | tee -a "$f"
}

# delete only UAT Loop and clear its retained state topic, so the run can start again from a fresh device
do_clear_loop() {
  local sid uuid
  EID=$(entry_id)
  sid=$(sub_field "$LOOP_NAME" 3)
  uuid=$(sub_field "$LOOP_NAME" 4)
  [ -n "$sid" ] && "$G" a ws raw config_entries/subentries/delete "{\"entry_id\":\"$EID\",\"subentry_id\":\"$sid\"}" >/dev/null && echo "removed: $LOOP_NAME"
  sleep 20
  [ -n "$uuid" ] && probe_pub -t "mqtt_actions/v1/devices/$uuid/state" -n -r
  echo "retained topics left under the removed device (empty is clean):"
  [ -n "$uuid" ] && probe_sub -t "mqtt_actions/v1/devices/$uuid/#" -v -W 3 -F '%t %r' 2>/dev/null
  true
}

# ---- P2-2 run ----------------------------------------------------------------------------------------------------------------
CAP=""
cap_pid=""
UUID=""
TOPIC=""
VERDICT_LINES=()
vline() { VERDICT_LINES+=("$1"); echo "$1"; }
live_count() { grep -v '^#' "$CAP" 2>/dev/null | grep -c ' r=0 ' || true; }
cleanup_probe() {
  if [ -n "$cap_pid" ]; then
    pkill -P "$cap_pid" 2>/dev/null
    kill "$cap_pid" 2>/dev/null
    cap_pid=""
  fi
}
runaway_guard() {
  local n
  n=$(live_count)
  if [ "${n:-0}" -gt 50 ]; then
    cleanup_probe
    "$G" a ws raw config_entries/subentries/delete "{\"entry_id\":\"$EID\",\"subentry_id\":\"$(sub_field "$LOOP_NAME" 3)\"}" >/dev/null 2>&1
    vline "FAIL runaway: $n live messages (> 50); device deleted, T-08-19"
    finish FAIL
  fi
}
finish() { # finish PASS|FAIL|ABORT
  cleanup_probe
  mkdir -p "$E2"
  {
    echo "$1"
    printf '%s\n' "${VERDICT_LINES[@]}"
  } >"$E2/verdict.txt"
  cp "$E2/verdict.txt" "$E2/result.txt"
  {
    echo
    echo "scripted run of check-p22.sh run, build $(sed -n 's/^sha: //p' "$EV/00-preflight/build.txt" | head -n1), $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "owner part (card rendering EN and DE, restart and release as seen in the frontend) is judged in the checkpoint, not here."
  } >>"$E2/result.txt"
  echo "$1"
  case "$1" in PASS) exit 0 ;; FAIL) exit 1 ;; *) exit 2 ;; esac
}
ext() { # ext VALUE : external publisher, retained like a real state change, QoS 1
  bridge_pub -t "$TOPIC" -m "$1" -q 1 -r
}
retained_value() { probe_sub -t "$TOPIC" -C 1 -W 4 -F '%p' 2>/dev/null; }
opposite() { [ "$1" = ON ] && echo OFF || echo ON; }
has_issue() { issues | grep -qx "mqtt_actions circuit_breaker_$UUID"; }
issue_snapshot() { # issue_snapshot LABEL
  {
    echo "[$1] $(date -u +%H:%M:%S) mqtt_actions issues:"
    issues | grep '^mqtt_actions ' | sed 's/^/  /'
  } >>"$E2/issues.txt"
}
wait_issue() { # wait_issue present|absent SECONDS ; polls every 2 s with the runaway guard
  local want=$1 max=$2 i
  for ((i = 0; i < max; i += 2)); do
    runaway_guard
    if has_issue; then [ "$want" = present ] && return 0; else [ "$want" = absent ] && return 0; fi
    sleep 2
  done
  return 1
}
wait_delta() { # wait_delta BEFORE EXACT SECONDS : wait, then return the delta of live messages
  sleep "$3"
  runaway_guard
  echo $(($(live_count) - $1))
}

do_run() {
  EID=$(entry_id)
  UUID=$(fx_get LOOP_ID)
  [ -n "$UUID" ] && [ -n "$(sub_field "$LOOP_NAME" 3)" ] || {
    VERDICT_LINES=("no $LOOP_NAME on ha-a; run setup first")
    finish ABORT
  }
  TOPIC="mqtt_actions/v1/devices/$UUID/state"
  mkdir -p "$E2"
  CAP="$E2/topic-capture.txt"
  : >"$E2/issues.txt"
  "$here/check-preflight.sh" --quick >/dev/null || {
    VERDICT_LINES=("check-preflight.sh --quick does not print PASS")
    finish ABORT
  }
  trap cleanup_probe EXIT
  # preconditions: nothing retained on the state topic of the fresh device, no tripped issue yet, no loop approval on ha-b
  local pre
  pre=$(retained_value)
  [ -z "$pre" ] || {
    VERDICT_LINES=("state topic of the loop device holds a retained value before the run: $pre")
    finish ABORT
  }
  has_issue && {
    VERDICT_LINES=("breaker issue already present before the run")
    finish ABORT
  }
  {
    echo "# live capture of $TOPIC (probe client, started before the first external publish)"
    echo "# format: ISO time, topic, r=<retain flag> then payload; r=0 lines are live messages, r=1 is the retained replay at subscribe"
  } >"$CAP"
  probe_sub -t "$TOPIC" -v -q 1 -W 1500 -F '%I %t r=%r %p' >>"$CAP" 2>/dev/null &
  cap_pid=$!
  sleep 3
  local t0 n1 n2 v warn
  t0=$(date -u +%Y-%m-%dT%H:%M:%S)

  # step 3: trip
  ext ON
  vline "step 3: external ON published (retained, QoS 1)"
  wait_issue present 15 || vline "FAIL step 3: no circuit_breaker issue within 15 s"
  sleep 5
  runaway_guard
  n1=$(live_count)
  issue_snapshot "after trip"
  vline "step 3: live messages on the state topic after the trip: $n1 (expected 6, accepted range 5..8)"
  { [ "$n1" -ge 5 ] && [ "$n1" -le 8 ]; } || vline "FAIL step 3: live message count $n1 outside 5..8"
  has_issue || vline "FAIL step 3: issue circuit_breaker_$UUID not listed"
  warn=$(podman logs --since "$t0" ha-a 2>&1 | grep -c "Circuit breaker tripped for device $LOOP_NAME")
  podman logs --since "$t0" ha-a 2>&1 | grep -E "Circuit breaker|UAT Loop" | sed 's/^/  /' >"$E2/log-a.txt"
  vline "step 3: breaker warnings in the log of ha-a since the run started: $warn (expected exactly 1)"
  [ "$warn" -eq 1 ] || vline "FAIL step 3: expected exactly one tripped warning, found $warn"

  # paused: external opposite adds exactly one message
  v=$(opposite "$(retained_value)")
  n1=$(live_count)
  ext "$v"
  n2=$(wait_delta "$n1" 1 10)
  vline "step 3b (paused): external $v, live message delta $n2 (expected exactly 1)"
  [ "$n2" -eq 1 ] || vline "FAIL step 3b: expected +1 live message while paused, got $n2"

  # step 5: restart while paused
  vline "step 5: podman restart ha-a ..."
  podman restart ha-a >/dev/null 2>&1 || vline "FAIL step 5: podman restart failed"
  wait_http 8123 || {
    vline "ABORT step 5: ha-a did not come back"
    finish ABORT
  }
  sleep 90
  runaway_guard
  has_issue && vline "step 5: issue still listed after the restart" || vline "FAIL step 5: issue gone after the restart"
  issue_snapshot "after restart"
  podman logs --since "$t0" ha-a 2>&1 | grep -E "Circuit breaker|UAT Loop" | sed 's/^/  /' >"$E2/log-a.txt"
  v=$(opposite "$(retained_value)")
  n1=$(live_count)
  ext "$v"
  n2=$(wait_delta "$n1" 1 15)
  vline "step 5b (paused across the restart): external $v, live message delta $n2 (expected exactly 1)"
  [ "$n2" -eq 1 ] || vline "FAIL step 5b: expected +1 live message after the restart, got $n2"

  # step 6: release by reload, then re-trip
  local ent
  ent=$(entry_id)
  "$G" a rest POST "/api/config/config_entries/entry/$ent/reload" '{}' | jq -c '{require_restart}' >>"$E2/issues.txt" 2>/dev/null
  vline "step 6: hub entry reloaded"
  if wait_issue absent 20; then vline "step 6: issue gone after the reload"; else vline "FAIL step 6: issue still listed 20 s after the reload"; fi
  issue_snapshot "after release"
  sleep 5
  v=$(opposite "$(retained_value)")
  n1=$(live_count)
  ext "$v"
  vline "step 6b: external $v published after the release"
  wait_issue present 20 || vline "FAIL step 6b: no circuit_breaker issue within 20 s after the renewed loop"
  sleep 5
  runaway_guard
  n2=$(($(live_count) - n1))
  vline "step 6b: new live messages after the release: $n2 (expected 6, accepted range 5..8: it ran, then tripped again)"
  { [ "$n2" -ge 5 ] && [ "$n2" -le 8 ]; } || vline "FAIL step 6b: delta $n2 outside 5..8"
  has_issue && vline "step 6b: issue present again at the end (left in place for the owner's live look)" || vline "FAIL step 6b: issue not present at the end"
  issue_snapshot "after re-trip"
  podman logs --since "$t0" ha-a 2>&1 | grep -E "Circuit breaker|UAT Loop" | sed 's/^/  /' >"$E2/log-a.txt"
  vline "total live messages in the capture: $(live_count)"

  if printf '%s\n' "${VERDICT_LINES[@]}" | grep -q '^FAIL\|^ABORT'; then finish FAIL; else finish PASS; fi
}

# ---- teardown ------------------------------------------------------------------------------------------------------------------
do_teardown() {
  local ent title sid
  EID=$(entry_id)
  "$G" a rest POST "/api/config/config_entries/entry/$EID/reload" '{}' >/dev/null 2>&1
  sleep 10
  while IFS=$'\t' read -r _t title sid _u; do
    case "$title" in
      "$LOOP_NAME" | "UAT P2-"*)
        "$G" a ws raw config_entries/subentries/delete "{\"entry_id\":\"$EID\",\"subentry_id\":\"$sid\"}" >/dev/null
        echo "removed: $title"
        ;;
    esac
  done < <(subs)
  sleep 20
}

do_peek() {
  cfg_doc "$1" | jq -c 'paths(scalars) | map(tostring) | join(".")' | head -60
}

mode=${1:-}
[ $# -gt 0 ] && shift
case "$mode" in
  p21) do_p21 ;;
  setup) do_setup ;;
  run) do_run ;;
  teardown) do_teardown ;;
  clear-loop) do_clear_loop ;;
  peek) do_peek "$@" ;;
  *)
    echo "usage: check-p22.sh p21|setup|run|teardown|peek ID" >&2
    exit 2
    ;;
esac
