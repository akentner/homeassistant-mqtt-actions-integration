#!/usr/bin/env bash
# Phase 8, plan 08-08: P1-2 (hub flow strings) and P3-1 (hostile approval request). Lives outside the repository.
#
#   check-p12.sh wait-b            wait until ha-b answers on 8124
#   check-p12.sh remove-hub        record ha-b's hub state (entry id and instance id only), then remove the hub of ha-b through the
#                                  config entries REST endpoint (device removal option left at its default: off)
#   check-p12.sh after-add         after the owner re-added the hub: read the new instance id (one field), write p1-2/new-instance-id.txt
#                                  and ~/ha-test/.instance-ids.env, add the availability line to the ha_two ACL block, HUP mosq, reload
#                                  the hub entry of ha-b, probe availability and heartbeat, watch for native_cutover_waiting
#   check-p12.sh import-hostile    import the hostile device on ha-b (inert), wait for the unapproved request on ha-a
#   check-p12.sh approve-marker    restore the approval of the marker mirror on ha-b (approvals are removed with the hub)
#   check-p12.sh delete-hostile    delete the hostile device on ha-b through the integration's delete step (subentry flow menu
#                                  delete_device > delete_confirmed), write p3-1/topics-after-delete.txt (retained topics, subentry,
#                                  request on ha-a)
#
# Only ha-b is driven for changes; ha-a is only read (and never approves the hostile device). Run from inside a checkout. Exit 0 PASS,
# 1 FAIL, 2 ABORT/usage.
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"
G="$here/ha-test-guard"
FX="$HT/.fixtures-frontend.env"
EV=$(evidence_root)
E12="$EV/p1-2"
E31="$EV/p3-1"
ACL="$HT/mosquitto/acl"
OLD_ID_B=a09499e4-5674-48d5-b3d6-4860d5226fcb

fx_get() { sed -n "s/^$1=//p" "$FX" 2>/dev/null | head -n1; }
fx_set() {
  touch "$FX"
  chmod 600 "$FX"
  grep -v "^$1=" "$FX" >"$FX.new" || true
  echo "$1=$2" >>"$FX.new"
  mv "$FX.new" "$FX"
}
entry_b() { "$G" b rest GET /api/config/config_entries/entry | jq -r '[.[] | select(.domain=="mqtt_actions")][0].entry_id // empty'; }
issues_b() { "$G" b ws raw repairs/list_issues | jq -r '.result.issues[] | "\(.domain) \(.issue_id)"'; }
issues_a() { "$G" a ws raw repairs/list_issues | jq -r '.result.issues[] | "\(.domain) \(.issue_id)"'; }
stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }

do_remove_hub() {
  mkdir -p "$E12"
  local eid
  eid=$(entry_b)
  [ -n "$eid" ] || {
    echo "ABORT ha-b has no mqtt_actions entry"
    return 2
  }
  # the backup must exist before the destructive step
  local bk
  bk=$(cat "$HT/.current-backup-p12" 2>/dev/null)
  [ -d "$bk/b/.storage" ] || {
    echo "ABORT no verified backup folder named in .current-backup-p12"
    return 2
  }
  diff -rq "$HT/b/.storage" "$bk/b/.storage" >/dev/null 2>&1 || echo "note: .storage of ha-b changed since the backup (live instance); the backup stays the restore point"
  {
    echo "ha-b hub before removal ($(stamp))"
    echo "entry id: $eid"
    echo "old instance id: $(jq -r '.data.entries[] | select(.domain=="mqtt_actions") | .data.instance_id' "$HT/b/.storage/core.config_entries")"
    echo "backup: ${bk/#$HOME/~}"
  } >"$E12/hub-before.txt"
  cat "$E12/hub-before.txt"
  resp=$("$G" b rest DELETE "/api/config/config_entries/entry/$eid")
  echo "remove response: $(jq -c . <<<"$resp" 2>/dev/null || echo "$resp")"
  sleep 5
  [ -z "$(entry_b)" ] || {
    echo "FAIL the hub entry of ha-b still exists"
    return 1
  }
  echo "PASS hub of ha-b removed"
}

do_after_add() {
  mkdir -p "$E12"
  local nid eid i st n hb
  nid=$(jq -r '.data.entries[] | select(.domain=="mqtt_actions") | .data.instance_id // empty' "$HT/b/.storage/core.config_entries" | head -n1)
  [[ "$nid" =~ ^[0-9a-f-]{36}$ ]] || {
    echo "ABORT no instance id of a new hub on ha-b"
    return 2
  }
  [ "$nid" != "$OLD_ID_B" ] || {
    echo "ABORT ha-b still has the old instance id"
    return 2
  }
  echo "INSTANCE_ID_B=$nid" >"$HT/.instance-ids.env"
  grep -q "$nid" "$ACL" || {
    cp -p "$ACL" "$ACL.bak-phase8-08"
    # insert after the old ha_two availability line, keep the old line (the old id is gone but harmless)
    awk -v old="$OLD_ID_B" -v new="$nid" '
      { print }
      $0 ~ ("instances/" old "/availability") { print "topic write mqtt_actions/v1/instances/" new "/availability" }' "$ACL.bak-phase8-08" >"$ACL.new"
    chmod --reference="$ACL.bak-phase8-08" "$ACL.new"
    mv "$ACL.new" "$ACL"
  }
  diff -u "$ACL.bak-phase8-08" "$ACL" >"$E12/acl-diff.txt" || true
  cat "$E12/acl-diff.txt"
  podman kill --signal HUP mosq >/dev/null
  sleep 3
  eid=$(entry_b)
  "$G" b rest POST "/api/config/config_entries/entry/$eid/reload" >/dev/null
  sleep 5
  st=""
  hb=0
  for i in $(seq 1 15); do
    st=$(probe_sub -t "mqtt_actions/v1/instances/$nid/availability" -F '%r %p' -W 3 2>/dev/null | head -n1)
    [ "$st" = "1 online" ] && break
    sleep 2
  done
  probe_sub -t "mqtt_actions/v1/instances/$nid/heartbeat" -F '%t' -W 60 -C 1 2>/dev/null | grep -q "$nid" && hb=1
  {
    echo "ha-b new instance id: $nid"
    echo "recorded: $(stamp)"
    echo "acl line: topic write mqtt_actions/v1/instances/$nid/availability (ha_two block)"
    echo "probe availability (retained flag, payload): ${st:-none}"
    echo "probe heartbeat within 60 s: $([ "$hb" = 1 ] && echo heard || echo NOT heard)"
  } >"$E12/new-instance-id.txt"
  # native_cutover_waiting: poll up to 5 min
  n=1
  for i in $(seq 1 30); do
    if issues_b | grep -q '^mqtt_actions native_cutover_waiting'; then
      sleep 10
    else
      n=0
      break
    fi
  done
  echo "native_cutover_waiting on ha-b after polling: $([ "$n" = 0 ] && echo none || echo STILL PRESENT)" | tee -a "$E12/new-instance-id.txt"
  cat "$E12/new-instance-id.txt"
  [ "$st" = "1 online" ] && [ "$hb" = 1 ] && [ "$n" = 0 ] && echo "PASS after-add" || {
    echo "FAIL after-add"
    return 1
  }
}

do_approve_marker() {
  local mid n resp fid
  mid=$(sed -n 's/^MARKER_ID=//p' "$HT/.fixtures.env" | head -n1)
  for i in $(seq 1 30); do
    n=$("$G" b ws raw repairs/list_issues | jq -r --arg id "approval_$mid" '[.result.issues[] | select(.issue_id==$id)] | length')
    [ "$n" = 1 ] && break
    sleep 2
  done
  [ "$n" = 1 ] || {
    echo "no pending approval issue for the marker on ha-b (found ${n:-none})"
    return 1
  }
  resp=$("$G" b rest POST /api/repairs/issues/fix "$(jq -n --arg id "approval_$mid" '{handler:"mqtt_actions", issue_id:$id}')")
  fid=$(jq -r '.flow_id // empty' <<<"$resp")
  [ -n "$fid" ] || {
    echo "no repairs flow: $(jq -c '{type,message}' <<<"$resp")"
    return 1
  }
  resp=$("$G" b rest POST "/api/repairs/issues/fix/$fid" '{}')
  echo "repairs flow result: $(jq -r '.type' <<<"$resp")"
  sleep 5
  n=$("$G" b ws raw repairs/list_issues | jq -r --arg id "approval_$mid" '[.result.issues[] | select(.issue_id==$id)] | length')
  [ "$n" = 0 ] && echo "PASS marker approved on ha-b again" || {
    echo "FAIL marker approval still pending"
    return 1
  }
}

# ---- P3-1 hostile device owned by ha-b --------------------------------------------------------------------------------
P31_NAME='UAT P3-1 `code` | _u_ <b>bold</b>'   # 33 printable characters (MAX_TEXT_LENGTH is 64)
P31_ACTION="{{ 'system_log' }}.write"           # templated service name; renders to system_log.write (not on the denylist)
P31_MESSAGE='UAT P3-1 `inert` | _text_'
hub_title_b() { "$G" b rest GET /api/config/config_entries/entry | jq -r '[.[] | select(.domain=="mqtt_actions")][0].title // empty'; }
subs_b() { # type, title, subentry_id, unique_id per line
  local eid
  eid=$(entry_b)
  "$G" b ws raw config_entries/subentries/list "{\"entry_id\":\"$eid\"}" |
    jq -r '.result[] | [.subentry_type, .title, .subentry_id, (.unique_id // "")] | @tsv'
}
retained_all_of() { probe_sub -t "mqtt_actions/v1/devices/$1/#" -v -W 3 -F '%t %r' 2>/dev/null || true; }
# import one inert switch on ha-b (same document shape as the export of uat-03/export-shape.json); prints its device uuid
import_device_b() { # NAME ACTIONS_JSON
  local name=$1 actions=$2 doc before after
  before=$(subs_b | cut -f4 | sort)
  doc=$(jq -nc --arg n "$name" --argjson a "$actions" \
    '{data:{format:"mqtt_actions_export",export_version:1,devices:[{kind:"switch",name:$n,on_change_to_on:$a,on_change_to_off:$a,run_mode:"serial",run_on_startup:false,breaker_max_runs:5,breaker_window:10}]}}')
  "$G" b ws call mqtt_actions.import_devices "$doc" >/dev/null || return 1
  sleep 6
  after=$(subs_b | cut -f4 | sort)
  comm -13 <(echo "$before") <(echo "$after") | head -n1
}

do_import_hostile() {
  mkdir -p "$E31"
  local actions uuid i seen=""
  actions=$(jq -nc --arg t "$P31_ACTION" --arg m "$P31_MESSAGE" '[{action:$t,data:{message:$m,level:"info"}}]')
  if [ -n "$(fx_get P31_ID)" ] && subs_b | cut -f4 | grep -qx "$(fx_get P31_ID)"; then
    uuid=$(fx_get P31_ID)
    echo "hostile device already on ha-b: $uuid"
  else
    uuid=$(import_device_b "$P31_NAME" "$actions")
    [ -n "$uuid" ] || {
      echo "FAIL import of the hostile device on ha-b gave no new device"
      return 1
    }
    fx_set P31_ID "$uuid"
  fi
  {
    echo "P3-1 hostile device imported on ha-b ($(stamp)) through ha-test-guard: ws call mqtt_actions.import_devices"
    echo "document shape (the export shape of 08-evidence/uat-03/export-shape.json, import_devices takes the same document):"
    echo "  {data: {format: mqtt_actions_export, export_version: 1, devices: [{kind: switch, name, on_change_to_on, on_change_to_off,"
    echo "   run_mode: serial, run_on_startup: false, breaker_max_runs: 5, breaker_window: 10}]}}  (on_change_to_off holds the same action)"
    echo "device name (${#P31_NAME} printable characters): $P31_NAME"
    echo "owner (instance) name of ha-b (hub entry title): $(hub_title_b)"
    echo "owner instance id: $(inst_id b)"
    echo "device id (P31_ID in ~/ha-test/.fixtures-frontend.env): $uuid"
    echo "on_change_to_on and on_change_to_off:"
    jq . <<<"$actions" | sed 's/^/  /'
    echo "the action value is a template that renders to system_log.write (not a denied service); the message holds backticks,"
    echo "underscores and a pipe; nothing calls a real service beyond the system log. The request is never approved on ha-a."
  } >"$E31/import-shape.txt"
  cat "$E31/import-shape.txt"
  # wait up to 2 min for the request on ha-a; an approval issue exists only while the mirror is unapproved
  for i in $(seq 1 60); do
    seen=$(issues_a | grep -E "^mqtt_actions (approval|blocked|denied_call)_$uuid\$" | head -n1)
    [ -n "$seen" ] && break
    sleep 2
  done
  echo "ha-a issue for $uuid after polling: ${seen:-none}" | tee -a "$E31/import-shape.txt"
  if [ "$seen" = "mqtt_actions approval_$uuid" ]; then
    "$G" a ws raw repairs/list_issues |
      jq -c --arg id "approval_$uuid" '.result.issues[] | select(.issue_id==$id) | {issue_id, is_fixable, severity, translation_key, ignored}' |
      tee -a "$E31/import-shape.txt"
    echo "PASS import-hostile: unapproved request listed on ha-a"
  else
    echo "FAIL import-hostile: expected approval_$uuid on ha-a"
    return 1
  fi
}

# subentry flow over REST on ha-b (the same steps the frontend drives)
fstart_b() { # TYPE SUBENTRY_ID
  local body
  body=$(jq -nc --arg e "$(entry_b)" --arg t "$1" --arg s "$2" '{handler:[$e,$t],subentry_id:$s}')
  "$G" b rest POST /api/config/config_entries/subentries/flow "$body"
}
fnext_b() { "$G" b rest POST "/api/config/config_entries/subentries/flow/$1" "$2"; }

do_delete_hostile() {
  mkdir -p "$E31"
  local uuid sid r fid f="$E31/topics-after-delete.txt" left=0 out
  uuid=$(fx_get P31_ID)
  [ -n "$uuid" ] || {
    echo "ABORT no P31_ID recorded"
    return 2
  }
  sid=$(subs_b | awk -F'\t' -v u="$uuid" '$4 == u {print $3; exit}')
  if [ -n "$sid" ]; then
    r=$(fstart_b switch "$sid")
    fid=$(jq -r '.flow_id // empty' <<<"$r")
    [ -n "$fid" ] || {
      echo "FAIL no reconfigure flow for the hostile device: $(jq -c '{type,reason}' <<<"$r")"
      return 1
    }
    r=$(fnext_b "$fid" '{"next_step_id":"delete_device"}')
    echo "delete_device step: $(jq -c '{type, step_id, menu_options, placeholders: .description_placeholders}' <<<"$r")"
    r=$(fnext_b "$fid" '{"next_step_id":"delete_confirmed"}')
    echo "delete_confirmed step: $(jq -c '{type, reason}' <<<"$r")"
    [ "$(jq -r '.reason // empty' <<<"$r")" = device_deleted ] || {
      echo "FAIL the integration's delete step did not end with device_deleted"
      return 1
    }
    sleep 20
  else
    echo "hostile device subentry already gone on ha-b"
  fi
  {
    echo "# retained topics under mqtt_actions/v1/devices/$uuid/# read back after the delete ($(stamp))"
    echo "device: $P31_NAME uuid: $uuid (deleted through the integration's delete step of the subentry flow on ha-b)"
    out=$(retained_all_of "$uuid")
    if [ -z "$out" ]; then echo "  retained topics: none (empty)"; else
      echo "$out" | sed 's/^/  /'
      left=1
    fi
    if subs_b | cut -f4 | grep -qx "$uuid"; then
      echo "  subentry on ha-b: STILL PRESENT"
      left=1
    else echo "  subentry on ha-b: gone"; fi
    if issues_a | grep -q "^mqtt_actions approval_$uuid\$"; then
      echo "  approval request on ha-a: STILL LISTED"
      left=1
    else echo "  approval request on ha-a: gone"; fi
  } >"$f"
  cat "$f"
  [ "$left" -eq 0 ] && echo "PASS delete-hostile" || {
    echo "FAIL delete-hostile"
    return 1
  }
}

mode=${1:-}
[ $# -gt 0 ] && shift
case "$mode" in
  wait-b) wait_http 8124 && echo "ha-b up" ;;
  remove-hub) do_remove_hub ;;
  after-add) do_after_add ;;
  approve-marker) do_approve_marker ;;
  import-hostile) do_import_hostile ;;
  delete-hostile) do_delete_hostile ;;
  *)
    echo "usage: check-p12.sh wait-b|remove-hub|after-add|approve-marker|import-hostile|delete-hostile" >&2
    exit 2
    ;;
esac
