#!/usr/bin/env bash
# Frontend-check bench helper for the Phase 8 human-verification items (plans 08-06, 08-07, 08-08). Lives outside the repository.
#
#   check-frontend.sh baseline              snapshot ha-a before any throwaway device exists (subentry titles, retained config ids)
#   check-frontend.sh fixtures ID...        create the throwaway fixtures of the items (idempotent): p1-4 p3-2
#   check-frontend.sh prep ID...            assert the item is ready for the owner: screenshots or the browser-unavailable note,
#                                           fixtures as expected, evidence scan clean. IDs: p1-3 p1-4 p3-2
#   check-frontend.sh readback p3-2         write p3-2/topics-after-delete.txt and assert both hostile devices are gone and empty
#   check-frontend.sh remove                delete every throwaway "UAT P*" subentry on ha-a through the guard and wait
#   check-frontend.sh cleanup               assert ha-a is back to its baseline (devices, retained config topics, failure issues)
#
# Only ha-a is touched (ha-test-guard letter a). Run from inside a checkout (the evidence folder comes from the git toplevel).
# Exit 0 PASS, 1 FAIL, 2 usage.
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"
G="$here/ha-test-guard"
FX="$HT/.fixtures-frontend.env"
BASE="$HT/.frontend-baseline.txt"
EV=$(evidence_root)

P32A_NAME='UAT P3-2a `code` <b>bold</b>'
P32B_NAME='UAT P3-2b `code` <b>bold</b>'
P14_NAME='UAT P1-4'

entry_id() { "$G" a rest GET /api/config/config_entries/entry | jq -r '[.[] | select(.domain=="mqtt_actions")][0].entry_id'; }
subs() { # type, title, subentry_id, unique_id per line
  local eid
  eid=$(entry_id)
  "$G" a ws raw config_entries/subentries/list "{\"entry_id\":\"$eid\"}" |
    jq -r '.result[] | [.subentry_type, .title, .subentry_id, (.unique_id // "")] | @tsv'
}
retained_ids() { probe_sub -t 'mqtt_actions/v1/devices/+/config' -v -W 3 -F '%t' 2>/dev/null |
  sed -n 's#^mqtt_actions/v1/devices/\([^/]*\)/config$#\1#p' | sort; }
retained_all_of() { probe_sub -t "mqtt_actions/v1/devices/$1/#" -v -W 3 -F '%t %r' 2>/dev/null || true; }
issues() { "$G" a ws raw repairs/list_issues | jq -r '.result.issues[] | "\(.domain) \(.issue_id)"'; }
fx_get() { sed -n "s/^$1=//p" "$FX" 2>/dev/null | head -n1; }
fx_set() { # fx_set KEY VALUE
  touch "$FX"
  chmod 600 "$FX"
  grep -v "^$1=" "$FX" >"$FX.new" || true
  echo "$1=$2" >>"$FX.new"
  mv "$FX.new" "$FX"
}

# import one inert device on ha-a; prints its device uuid (the unique id of the new subentry)
import_device() { # NAME ACTIONS_JSON
  local name=$1 actions=$2 doc before after
  before=$(subs | cut -f4 | sort)
  doc=$(jq -nc --arg n "$name" --argjson a "$actions" \
    '{data:{format:"mqtt_actions_export",export_version:1,devices:[{kind:"switch",name:$n,on_change_to_on:$a,on_change_to_off:$a,run_mode:"serial",run_on_startup:false,breaker_max_runs:5,breaker_window:10}]}}')
  "$G" a ws call mqtt_actions.import_devices "$doc" >/dev/null || return 1
  sleep 6
  after=$(subs | cut -f4 | sort)
  comm -13 <(echo "$before") <(echo "$after") | head -n1
}

do_baseline() {
  {
    subs | cut -f1,2 | sed 's/^/sub\t/'
    retained_ids | sed 's/^/topic\t/'
  } >"$BASE"
  chmod 600 "$BASE"
  echo "baseline written: $(grep -c '^sub' "$BASE") devices, $(grep -c '^topic' "$BASE") retained config topics"
}

do_fixtures() {
  [ -f "$BASE" ] || {
    echo "FAIL no baseline; run baseline first"
    return 1
  }
  local id
  for id in "$@"; do
    case "$id" in
      p1-4)
        if [ -z "$(fx_get P14_ID)" ] || ! subs | cut -f4 | grep -qx "$(fx_get P14_ID)"; then
          u=$(import_device "$P14_NAME" '[{"action":"uat_missing.nothing"}]')
          [ -n "$u" ] || {
            echo "FAIL import of $P14_NAME gave no new device"
            return 1
          }
          fx_set P14_ID "$u"
        fi
        ;;
      p3-2)
        if [ -z "$(fx_get P32A_ID)" ] || ! subs | cut -f4 | grep -qx "$(fx_get P32A_ID)"; then
          u=$(import_device "$P32A_NAME" '[{"action":"system_log.write","data":{"message":"UAT P3-2 inert","level":"info"}}]')
          [ -n "$u" ] || {
            echo "FAIL import of P3-2a gave no new device"
            return 1
          }
          fx_set P32A_ID "$u"
        fi
        if [ -z "$(fx_get P32B_ID)" ] || ! subs | cut -f4 | grep -qx "$(fx_get P32B_ID)"; then
          u=$(import_device "$P32B_NAME" '[{"action":"system_log.write","data":{"message":"UAT P3-2 inert","level":"info"}}]')
          [ -n "$u" ] || {
            echo "FAIL import of P3-2b gave no new device"
            return 1
          }
          fx_set P32B_ID "$u"
        fi
        ;;
      *)
        echo "unknown fixture id $id"
        return 2
        ;;
    esac
  done
  echo "fixtures ready: $*"
}

# toggle UAT P1-4 on and wait (at most 90 s) until its failure issue is listed
do_p14_trigger() {
  local ent i
  ent=$("$G" a ws raw get_states | jq -r --arg n "$P14_NAME" '[.result[] | select(.attributes.friendly_name==$n)][0].entity_id // empty')
  [ -n "$ent" ] || {
    echo "FAIL no entity named $P14_NAME on ha-a"
    return 1
  }
  "$G" a ws call switch.turn_on "{\"entity_id\":\"$ent\"}" >/dev/null || return 1
  for ((i = 0; i < 45; i++)); do
    if issues | grep -q "^mqtt_actions action_failed_$(fx_get P14_ID)\$"; then
      echo "failure issue present for $ent"
      return 0
    fi
    sleep 2
  done
  echo "FAIL no failure issue within 90 s"
  return 1
}

prep_one() {
  local id=$1 dir="$EV/$1" n shots
  shots=$(find "$dir" -maxdepth 1 -name '*.png' -size +0 2>/dev/null | wc -l)
  [ -s "$dir/screens.txt" ] || chk_fail "$id: screens.txt missing or empty"
  if [ "$id" = p1-3 ] || [ "$shots" -eq 0 ]; then
    grep -q 'browser-mcp: unavailable' "$EV/p1-3/browser.txt" 2>/dev/null || [ "$shots" -gt 0 ] ||
      chk_fail "$id: neither screenshots nor the browser-unavailable note"
  fi
  [ -s "$EV/p1-3/browser.txt" ] || chk_fail "p1-3/browser.txt missing"
  case "$id" in
    p1-3) : ;; # fixtures are made by the click path itself
    p1-4)
      subs | cut -f2 | grep -qx "$P14_NAME" || chk_fail "p1-4: fixture $P14_NAME missing on ha-a"
      issues | grep -q "^mqtt_actions action_failed_$(fx_get P14_ID)\$" || chk_fail "p1-4: failure issue of $P14_NAME missing"
      ;;
    p3-2)
      if [ "$shots" -gt 0 ]; then
        for k in P32A_ID P32B_ID; do
          n=$(retained_all_of "$(fx_get $k)" | wc -l)
          [ "$n" -eq 0 ] || chk_fail "p3-2: $k still retained on the broker"
        done
      else
        subs | cut -f4 | grep -qx "$(fx_get P32A_ID)" || chk_fail "p3-2: hostile device a missing (owner has not deleted it yet)"
        subs | cut -f4 | grep -qx "$(fx_get P32B_ID)" || chk_fail "p3-2: hostile device b missing (owner has not deleted it yet)"
      fi
      ;;
    p2-1)
      subs | cut -f2 | grep -qx "UAT P2-1" || chk_fail "p2-1: fixture UAT P2-1 missing on ha-a"
      [ -s "$dir/flow-precheck.txt" ] || chk_fail "p2-1: flow-precheck.txt missing"
      ;;
    p2-2)
      subs | cut -f2 | grep -qx "UAT Loop" || chk_fail "p2-2: fixture UAT Loop missing on ha-a"
      issues | grep -q "^mqtt_actions circuit_breaker_$(fx_get LOOP_ID)\$" || chk_fail "p2-2: UAT Loop is not tripped"
      [ -s "$dir/loop-config.txt" ] || chk_fail "p2-2: loop-config.txt missing"
      head -n1 "$dir/verdict.txt" 2>/dev/null | grep -q '^PASS\|^FAIL' || chk_fail "p2-2: verdict.txt is not PASS or FAIL"
      ;;
    p1-2)
      # ha-b has a new hub (instance id equals the env file), no cutover wait, availability read back; P1-2 has no fixture on ha-a
      local nid
      nid=$(jq -r '.data.entries[] | select(.domain=="mqtt_actions") | .data.instance_id // empty' "$HT/b/.storage/core.config_entries" 2>/dev/null | head -n1)
      { [ -n "$nid" ] && [ "$nid" = "$(inst_id b)" ]; } || chk_fail "p1-2: ha-b has no hub with the instance id of .instance-ids.env"
      [ "$nid" != a09499e4-5674-48d5-b3d6-4860d5226fcb ] || chk_fail "p1-2: ha-b still has the old instance id"
      "$G" b ws raw repairs/list_issues | jq -e '[.result.issues[] | select(.issue_id=="native_cutover_waiting")] | length == 0' >/dev/null ||
        chk_fail "p1-2: ha-b shows native_cutover_waiting"
      grep -q 'probe availability (retained flag, payload): 1 online' "$dir/new-instance-id.txt" 2>/dev/null ||
        chk_fail "p1-2: new-instance-id.txt has no online availability read-back"
      grep -q 'probe heartbeat within 60 s: heard' "$dir/new-instance-id.txt" 2>/dev/null ||
        chk_fail "p1-2: new-instance-id.txt has no heartbeat read-back"
      grep -q "$nid" "$dir/acl-diff.txt" 2>/dev/null || chk_fail "p1-2: acl-diff.txt does not show the new instance id"
      [ -d "$(cat "$HT/.current-backup-p12" 2>/dev/null)" ] || chk_fail "p1-2: backup folder of .current-backup-p12 missing"
      ;;
    p3-1)
      # the hostile device is owned by ha-b; its approval request is open on ha-a and must NOT have been approved
      [ -n "$(fx_get P31_ID)" ] || chk_fail "p3-1: no P31_ID recorded"
      issues | grep -q "^mqtt_actions approval_$(fx_get P31_ID)\$" || chk_fail "p3-1: the unapproved request is not listed on ha-a"
      [ -s "$dir/import-shape.txt" ] || chk_fail "p3-1: import-shape.txt missing"
      ;;
    *) chk_fail "unknown item $id" ;;
  esac
}

do_prep() {
  local id
  for id in "$@"; do prep_one "$id"; done
  "$here/check-evidence-clean.sh" "$EV" >/dev/null || chk_fail "evidence scan failed"
  chk_finish "check-frontend prep $*" "$EV"
}

do_readback() {
  local f="$EV/p3-2/topics-after-delete.txt" k id left=0 name
  mkdir -p "$EV/p3-2"
  {
    echo "# retained topics under mqtt_actions/v1/devices/{uuid}/# read back after the deletes ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
    for k in P32A_ID P32B_ID; do
      id=$(fx_get $k)
      name=$([ "$k" = P32A_ID ] && echo "integration delete step (device a)" || echo "generic core dialog (device b)")
      echo "device: $name uuid: $id"
      out=$(retained_all_of "$id")
      if [ -z "$out" ]; then echo "  retained topics: none (empty)"; else
        echo "$out" | sed 's/^/  /'
        left=1
      fi
      if subs | cut -f4 | grep -qx "$id"; then
        echo "  subentry: STILL PRESENT"
        left=1
      else echo "  subentry: gone"; fi
    done
  } >"$f"
  cat "$f"
  [ "$left" -eq 0 ] && echo "PASS readback p3-2" || {
    echo "FAIL readback p3-2"
    return 1
  }
}

do_remove() {
  local eid sid title
  eid=$(entry_id)
  while IFS=$'\t' read -r _t title sid _u; do
    case "$title" in
      "UAT P"* | "UAT Loop")
        "$G" a ws raw config_entries/subentries/delete "{\"entry_id\":\"$eid\",\"subentry_id\":\"$sid\"}" >/dev/null
        echo "removed: $title"
        ;;
    esac
  done < <(subs)
  sleep 15
}

do_cleanup() {
  local cur
  [ -f "$BASE" ] || {
    echo "FAIL no baseline"
    return 1
  }
  cur=$(subs | cut -f1,2 | sed 's/^/sub\t/' | sort)
  [ "$cur" = "$(grep '^sub' "$BASE" | sort)" ] || chk_fail "devices on ha-a differ from the baseline"
  [ "$(retained_ids | sed 's/^/topic\t/' | sort)" = "$(grep '^topic' "$BASE" | sort)" ] ||
    chk_fail "retained config topics differ from the baseline"
  issues | grep -q '^mqtt_actions action_failed_' && chk_fail "a failure issue is still listed on ha-a"
  issues | grep -q '^mqtt_actions circuit_breaker_' && chk_fail "a breaker issue is still listed on ha-a"
  # plan 08-08: the hostile device of P3-1 is owned by ha-b; its request, mirror and ha-b's hub state are checked here too
  if [ -n "$(fx_get P31_ID)" ]; then
    "$G" a ws raw repairs/list_issues | jq -e --arg id "approval_$(fx_get P31_ID)" '[.result.issues[] | select(.issue_id==$id)] | length == 0' >/dev/null ||
      chk_fail "P31_ID still has an approval issue on ha-a"
    "$G" a ws raw get_states | jq -e '[.result[] | select(.attributes.friendly_name | tostring | startswith("UAT P3-1"))] | length == 0' >/dev/null ||
      chk_fail "a P3-1 mirror is still on ha-a"
    "$G" b ws raw get_states | jq -e '[.result[] | select(.attributes.friendly_name | tostring | startswith("UAT P3-1"))] | length == 0' >/dev/null ||
      chk_fail "a P3-1 device is still on ha-b"
  fi
  if [ -f "$HT/.instance-ids.env" ]; then
    "$G" b rest GET /api/config/config_entries/entry | jq -e '[.[] | select(.domain=="mqtt_actions")] | length == 1' >/dev/null ||
      chk_fail "ha-b has no mqtt_actions hub entry"
    "$G" b ws raw repairs/list_issues | jq -e '[.result.issues[] | select(.issue_id=="native_cutover_waiting")] | length == 0' >/dev/null ||
      chk_fail "ha-b waits for a legacy peer (native_cutover_waiting)"
  fi
  for k in P14_ID P32A_ID P32B_ID P21_ID LOOP_ID P31_ID; do
    [ -n "$(fx_get $k)" ] || continue
    [ -z "$(retained_all_of "$(fx_get $k)")" ] || chk_fail "$k still retained on the broker"
    "$G" b ws raw repairs/list_issues | jq -e --arg id "approval_$(fx_get $k)" '[.result.issues[] | select(.issue_id==$id)] | length == 0' >/dev/null ||
      chk_fail "$k still has an approval issue on ha-b"
    "$G" b ws raw repairs/list_issues | jq -e --arg id "blocked_$(fx_get $k)" '[.result.issues[] | select(.issue_id==$id)] | length == 0' >/dev/null ||
      chk_fail "$k still has a blocked issue on ha-b"
  done
  "$G" b ws raw get_states | jq -e '[.result[] | select(.attributes.friendly_name | tostring | (startswith("UAT P") or startswith("UAT Loop")))] | length == 0' >/dev/null ||
    chk_fail "a throwaway UAT P mirror is still on ha-b"
  chk_finish "check-frontend cleanup" "ha-a"
}

mode=${1:-}
[ $# -gt 0 ] && shift
case "$mode" in
  baseline) do_baseline ;;
  fixtures) do_fixtures "$@" ;;
  trigger-p14) do_p14_trigger ;;
  prep) do_prep "$@" ;;
  readback) do_readback ;;
  remove) do_remove ;;
  cleanup) do_cleanup ;;
  *)
    echo "usage: check-frontend.sh baseline|fixtures ID...|trigger-p14|prep ID...|readback p3-2|remove|cleanup" >&2
    exit 2
    ;;
esac
