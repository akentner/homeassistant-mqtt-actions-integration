#!/usr/bin/env bash
# Isolated reproduction of UAT-04 clause 2 (enabled mqtt-platform export duplicates on the core prefix). Phase 8, plan 08-11.
#   check-uat04-iso.sh tracer          the clean arm end to end for ONE fresh device (task 1); writes tracer-* evidence
#   check-uat04-iso.sh verify --tracer assert the tracer evidence is complete and the bench is back at its baseline
# Run from inside the checkout that holds the evidence. Exit: 0 valid result, 1 failed verify, 2 ABORT (bench problem, never a result).
#
# HEADER BEGIN (the expectations are coded here BEFORE the first run, D-08; the run writes the sha256 of this block)
# Product contract P1 (the documented promise, README "MQTT Discovery export"): with the export on the core prefix
#   `homeassistant`, every instance holds, per exported device id, exactly ONE row with platform `mqtt`, unique id equal to
#   the device id and disabled_by `integration`; the native row (platform `mqtt_actions`, unique id equal to the device id)
#   stays enabled (disabled_by null). The native row is required on ha-a (the owner); on ha-b the mirror is never approved in
#   this plan, so a native row there is recorded without a judgement.
# Tracer rule (clean arm, ONE fresh device id that never had an mqtt-platform entity, read on the live registries of ha-a AND
#   ha-b before any restart):
#   CLEAN-ARM-DISABLED  on ha-a and on ha-b: exactly one mqtt row for the id and its disabled_by is `integration`
#   CLEAN-ARM-ENABLED   any other observation (zero or several rows, or a disabled_by other than `integration`)
# Context lines (recorded, never part of a rule): the mqtt rows of Lampe Test, Bar Select and UAT Marker on both instances.
# HEADER END
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
SELF=$(readlink -f "$0")
# shellcheck source=lib.sh
. "$here/lib.sh"
G="$here/ha-test-guard"

MODE=${1:-}
ARG=${2:-}
EV="$(evidence_root)/uat-04-isolation"
FXG="$HT/.fixtures-gap.env"
BACKUP_PTR="$HT/.current-backup-gap08"
CORE_PREFIX=homeassistant
EXPORT_PREFIX=mqtt_actions_export
WAIT_APPLY=20
SETTLE_SECONDS=90 # HA start plus the 5.0 s quiet period of the replay catch, with margin
ID_SWITCH=11111111-aaaa-4aaa-8aaa-000000000001 # Lampe Test
ID_SELECT=b6bd2c0e-6d81-49ea-8025-4bd087bd718a # Bar Select
ID_MARKER=$(sed -n 's/^MARKER_ID=//p' "$HT/.fixtures.env" 2>/dev/null | head -n1)

abort() {
  echo "ABORT $1" >&2
  exit 2
}

# ---- helpers ----------------------------------------------------------------------------------------------------------------
header_sha() { sed -n '/^# HEADER BEGIN/,/^# HEADER END/p' "$SELF" | sha256sum | cut -d' ' -f1; }
header_block() { sed -n '/^# HEADER BEGIN/,/^# HEADER END/p' "$SELF"; }
running() { [ "$(podman inspect "$1" --format '{{.State.Running}}' 2>/dev/null)" = true ]; }
started_at() { podman inspect "$1" --format '{{.State.StartedAt}}' 2>/dev/null | sed -e 's/ m=.*//'; }
stop_both() {
  podman stop -t 60 ha-a ha-b >/dev/null 2>&1
  { ! running ha-a && ! running ha-b; } || abort "ha-a and ha-b did not stop"
}
start_both() {
  podman start ha-a ha-b >/dev/null 2>&1 || abort "podman start failed"
  wait_http 8123 && wait_http 8124 || abort "an instance did not come up"
}
read_topics() { probe_sub -t "$1" -F '%t %r %p' -W 3 2>/dev/null; } # lines: topic retain payload
fx_get() { sed -n "s/^$1=//p" "$FXG" 2>/dev/null | head -n1; }
fx_set() { # fx_set KEY VALUE (ids only, no secrets)
  touch "$FXG"
  chmod 600 "$FXG"
  grep -v "^$1=" "$FXG" >"$FXG.new" || true
  echo "$1=$2" >>"$FXG.new"
  mv "$FXG.new" "$FXG"
}
entry_id() { "$G" "$1" ws raw config_entries/get | jq -r '[.result[] | select(.domain=="mqtt_actions") | .entry_id][0] // empty'; }
subs() { # subs LETTER : "subentry_id<TAB>unique_id<TAB>title" per line
  local eid
  eid=$(entry_id "$1")
  "$G" "$1" ws raw config_entries/subentries/list "{\"entry_id\":\"$eid\"}" |
    jq -r '.result[]? | [.subentry_id, (.unique_id // ""), .title] | @tsv'
}
live_rows() { # live registry of a running instance, fixed projection (ids and disabled_by only)
  "$G" "$1" ws raw config/entity_registry/list | jq -S '[.result[]
      | if (.platform == "mqtt" or .platform == "mqtt_actions")
        then {platform, entity_id, id, unique_id, device_id, disabled_by}
        elif (.entity_id | test("_2$")) then {platform, entity_id}
        else empty end]
      | sort_by(.entity_id, .unique_id)'
}
set_options() { # set_options LETTER EXPORT PREFIX LOGFILE
  local l=$1 on=$2 prefix=$3 log=$4 eid start flow sub
  eid=$(entry_id "$l")
  [ -n "$eid" ] || abort "no mqtt_actions config entry on ha-$l"
  start=$("$G" "$l" rest POST /api/config/config_entries/options/flow "{\"handler\":\"$eid\"}")
  flow=$(jq -r '.flow_id // empty' <<<"$start" 2>/dev/null)
  [ -n "$flow" ] || abort "the options flow did not start"
  sub=$("$G" "$l" rest POST "/api/config/config_entries/options/flow/$flow" \
    "{\"delete_devices_on_remove\":false,\"discovery_export\":$on,\"export_prefix\":\"$prefix\"}")
  echo "options flow ha-$l entry $eid: discovery_export=$on export_prefix=$prefix -> type=$(jq -r '.type // "-"' <<<"$sub") errors=$(jq -c '.errors // {}' <<<"$sub")" >>"$log"
  [ "$(jq -r '.type // empty' <<<"$sub")" = create_entry ] || abort "the options flow did not end in create_entry"
}
# import_switch NAME ON_MESSAGE OFF_MESSAGE : one inert switch on ha-a; prints its uuid
import_switch() {
  local body resp uuid
  body=$(jq -nc --arg n "$1" --arg on "$2" --arg off "$3" '{data:{format:"mqtt_actions_export",export_version:1,devices:[{
      kind:"switch",name:$n,
      on_change_to_on:[{action:"system_log.write",data:{message:$on,level:"warning"}}],
      on_change_to_off:[{action:"system_log.write",data:{message:$off,level:"warning"}}],
      run_mode:"serial",run_on_startup:false,breaker_max_runs:5,breaker_window:10}]}}')
  resp=$("$G" a rest POST '/api/services/mqtt_actions/import_devices?return_response' "$body")
  uuid=$(jq -r '.service_response.imported[0].uuid // empty' <<<"$resp")
  [ -n "$uuid" ] || abort "no uuid in the import response of $1"
  echo "$uuid"
}
mirror_present() { # mirror_present ID : ha-b holds a registry row of the mirror (mirrors are entities, not config subentries)
  "$G" b ws raw config/entity_registry/list | jq -e --arg id "$1" '[.result[]? | select(.platform == "mqtt_actions" and ((.unique_id // "") | startswith($id)))] | length > 0' >/dev/null
}
wait_mirror() { # wait_mirror ID : the mirror appears on ha-b (poll 2 s, at most 60 s)
  local i
  for ((i = 0; i < 30; i++)); do
    mirror_present "$1" && return 0
    sleep 2
  done
  return 1
}
# backup_registries : stop both gracefully, copy both entity registry files outside the repo, start both, wait, quick preflight
backup_registries() { # prints the backup path
  local stamp dir l
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  dir="$HT/_backup-pre-gap-uat04-$stamp"
  stop_both
  (umask 077 && mkdir -p "$dir/a" "$dir/b") || abort "cannot create $dir"
  chmod 700 "$dir" "$dir/a" "$dir/b"
  for l in a b; do cp -p "$HT/$l/.storage/core.entity_registry" "$dir/$l/core.entity_registry" || abort "backup copy of ha-$l failed"; done
  echo "$dir" >"$BACKUP_PTR"
  start_both
  sleep 45
  "$here/check-preflight.sh" --quick >/dev/null || abort "check-preflight.sh --quick does not print PASS after the start"
  echo "$dir"
}
# rows_for LETTER ID FILE : "count<TAB>disabled_by list" of the mqtt-platform rows with the unique id
rows_for() {
  jq -r --arg id "$2" '[.[] | select(.platform == "mqtt" and .unique_id == $id)] | [length, ([.[] | (.disabled_by // "null")] | join(","))] | @tsv' "$3"
}
# delete_fixture ID : owner delete on ha-a through the subentry delete command
delete_fixture() {
  local eid sid
  eid=$(entry_id a)
  sid=$(subs a | awk -F'\t' -v id="$1" '$2 == id {print $1}')
  [ -n "$sid" ] || abort "no subentry with unique id $1 on ha-a"
  "$G" a ws raw config_entries/subentries/delete "{\"entry_id\":\"$eid\",\"subentry_id\":\"$sid\"}" >/dev/null || abort "subentry delete failed"
}
# cleanup_round TAG ID... : one restart first (the replay catch removes the leftover disabled export rows only while the
# device still has its native twin, research Pitfall 4), then the owner delete, topics and mirrors asserted, the three gates
cleanup_round() {
  local tag=$1 id n rc g
  shift
  podman restart -t 60 ha-a ha-b >/dev/null 2>&1 || abort "podman restart failed"
  wait_http 8123 && wait_http 8124 || abort "an instance did not come up after the cleanup restart"
  sleep "$SETTLE_SECONDS"
  echo "[$tag] cleanup restart done, StartedAt ha-a $(started_at ha-a), ha-b $(started_at ha-b)" >>"$EV/cleanup.txt"
  for id in "$@"; do delete_fixture "$id"; done
  sleep 15
  for id in "$@"; do
    n=$(read_topics "mqtt_actions/v1/devices/$id/config" | grep -c .)
    [ "$n" = 0 ] && echo "[$tag] retained config topic of $id empty PASS" >>"$EV/cleanup.txt" ||
      echo "[$tag] retained config topic of $id NOT EMPTY FAIL" >>"$EV/cleanup.txt"
    if mirror_present "$id"; then
      echo "[$tag] mirror of $id still on ha-b FAIL" >>"$EV/cleanup.txt"
    else
      echo "[$tag] mirror of $id gone from ha-b PASS" >>"$EV/cleanup.txt"
    fi
    subs a | cut -f2 | grep -qx "$id" && echo "[$tag] device $id still on ha-a FAIL" >>"$EV/cleanup.txt"
  done
  for g in "check-uat02.sh clean" "check-uat04.sh clean" "check-preflight.sh --quick"; do
    # shellcheck disable=SC2086
    "$here/${g%% *}" ${g#* } >/dev/null 2>&1
    rc=$?
    [ "$rc" = 0 ] && echo "[$tag] $g PASS" >>"$EV/cleanup.txt" || echo "[$tag] $g FAIL (exit $rc)" >>"$EV/cleanup.txt"
  done
}
need_baseline() {
  "$here/check-preflight.sh" --quick >/dev/null || abort "precondition: check-preflight.sh --quick does not print PASS"
  "$here/check-uat02.sh" clean >/dev/null || abort "precondition: check-uat02.sh clean does not print PASS"
  "$here/check-uat04.sh" clean >/dev/null || abort "precondition: check-uat04.sh clean does not print PASS"
  "$here/check-marker.sh" approved >/dev/null || abort "precondition: check-marker.sh approved does not print PASS"
  [ -n "$ID_MARKER" ] || abort "no MARKER_ID in .fixtures.env"
  for l in a b; do
    [ "$(stat -c %a "$HT/.token-$l")" = 600 ] || abort "token file of ha-$l is not mode 0600"
  done
}

# ---- mode: tracer -----------------------------------------------------------------------------------------------------------
do_tracer() {
  local backup id l n d token sha f dev payload
  mkdir -p "$EV"
  sha=$(header_sha)
  header_block >"$EV/header-tracer.txt"
  need_baseline
  : >"$EV/options-flow.txt"
  : >"$EV/cleanup.txt"
  backup=$(backup_registries) || exit 2
  {
    echo "plan 08-11 task 1 (tracer), $(date -u +%FT%TZ)"
    echo "build: $(sed -n 's/^sha: //p' "$(evidence_root)/00-preflight/build.txt" | head -n1)"
    echo "backup of both core.entity_registry files (outside the repo, mode 0700): $backup"
    echo "StartedAt after the gate start: ha-a $(started_at ha-a), ha-b $(started_at ha-b)"
  } >"$EV/precheck.txt"

  id=$(import_switch "UAT Iso Clean" "UAT04-ISO clean on" "UAT04-ISO clean off")
  fx_set ISO_CLEAN_ID "$id"
  wait_mirror "$id" || abort "the mirror of $id did not appear on ha-b within 60 s"
  n=$(cat "$backup/a/core.entity_registry" "$backup/b/core.entity_registry" | grep -c -F "$id" || true)
  {
    echo "tracer fixture: UAT Iso Clean, switch, owner ha-a, actions system_log.write level warning (messages 'UAT04-ISO clean on' / 'UAT04-ISO clean off')"
    echo "ISO_CLEAN_ID=$id"
    echo "mirror on ha-b: present, never approved"
    echo "occurrences of the id in the two backup registry files: $n"
  } >"$EV/fixtures.txt"
  [ "$n" = 0 ] || abort "the fresh id occurs in a backup registry file ($n)"

  # export on the core prefix, no restart
  set_options a true "$CORE_PREFIX" "$EV/options-flow.txt"
  sleep "$WAIT_APPLY"
  f="$EV/tracer-topics.txt"
  read_topics "$CORE_PREFIX/device/$id/config" >"$f"
  [ -s "$f" ] || abort "no retained export payload on $CORE_PREFIX/device/$id/config after ${WAIT_APPLY} s"
  payload=$(sed -n '1s/^[^ ]* [^ ]* //p' "$f")
  {
    echo "retain flag: $(awk 'NR==1 {print $2}' "$f")"
    echo "components (key, platform, enabled_by_default): $(jq -rc '[.components | to_entries[] | {key, platform: .value.platform, enabled_by_default: .value.enabled_by_default}]' <<<"$payload")"
  } >>"$f"
  [ "$(sed -n 's/^retain flag: //p' "$f")" = 1 ] || abort "the export payload is not retained"
  [ "$(jq -r '[.components[] | select((.platform != "switch") and (.platform != "select"))] | length' <<<"$payload")" = 0 ] || abort "an export component is neither switch nor select"
  [ "$(jq -r '[.components[] | select(.enabled_by_default != false)] | length' <<<"$payload")" = 0 ] || abort "an export component is not enabled_by_default false"
  for l in a b; do live_rows "$l" >"$EV/tracer-registry-$l.json"; done

  # evaluate
  {
    echo "header-sha256: $sha"
    echo "ISO_CLEAN_ID: $id"
  } >"$EV/tracer-result.txt"
  token=CLEAN-ARM-DISABLED
  for l in a b; do
    IFS=$'\t' read -r n d < <(rows_for "$l" "$id" "$EV/tracer-registry-$l.json")
    echo "ha-$l: mqtt rows with unique id ISO_CLEAN_ID: $n, disabled_by: ${d:-none}" >>"$EV/tracer-result.txt"
    { [ "$n" = 1 ] && [ "$d" = integration ]; } || token=CLEAN-ARM-ENABLED
    echo "ha-$l: native rows with unique id ISO_CLEAN_ID (information): $(jq -rc --arg id "$id" '[.[] | select(.platform == "mqtt_actions" and .unique_id == $id) | (.disabled_by // "null")]' "$EV/tracer-registry-$l.json")" >>"$EV/tracer-result.txt"
  done
  for l in a b; do
    for dev in "$ID_SWITCH:Lampe Test" "$ID_SELECT:Bar Select" "$ID_MARKER:UAT Marker"; do
      IFS=$'\t' read -r n d < <(rows_for "$l" "${dev%%:*}" "$EV/tracer-registry-$l.json")
      echo "context ha-$l ${dev#*:}: mqtt rows $n, disabled_by: ${d:-none}" >>"$EV/tracer-result.txt"
    done
  done
  echo "$token" >>"$EV/tracer-result.txt"

  # export off (prefix back at the default), read back empty
  set_options a false "$EXPORT_PREFIX" "$EV/options-flow.txt"
  sleep "$WAIT_APPLY"
  {
    echo "== homeassistant/device/# (retained, 3 s)"
    read_topics 'homeassistant/device/#'
    echo "== mqtt_actions_export/# (retained, 3 s)"
    read_topics 'mqtt_actions_export/#'
    echo "== end"
  } >"$EV/tracer-topics-after-off.txt"
  [ -z "$(sed -n '/^== /!p' "$EV/tracer-topics-after-off.txt" | sed '/^$/d')" ] || echo "[tracer] export topics empty after off FAIL" >>"$EV/cleanup.txt"

  cleanup_round tracer "$id"
  {
    echo "tracer finished $(date -u +%FT%TZ): $token"
  } >>"$EV/precheck.txt"
  echo "tracer done: $token (see $EV/tracer-result.txt)"
}

# ---- mode: verify --tracer --------------------------------------------------------------------------------------------------
do_verify_tracer() {
  local f l id n
  for f in precheck.txt fixtures.txt options-flow.txt header-tracer.txt tracer-topics.txt tracer-topics-after-off.txt \
    tracer-registry-a.json tracer-registry-b.json tracer-result.txt cleanup.txt; do
    [ -s "$EV/$f" ] || chk_fail "evidence file missing or empty: $f"
  done
  id=$(sed -n 's/^ISO_CLEAN_ID: //p' "$EV/tracer-result.txt" 2>/dev/null | head -n1)
  [ -n "$id" ] || chk_fail "tracer-result.txt names no ISO_CLEAN_ID"
  grep -q '^header-sha256: [0-9a-f]\{64\}$' "$EV/tracer-result.txt" 2>/dev/null || chk_fail "tracer-result.txt has no header sha256 line"
  grep -qE '^(CLEAN-ARM-DISABLED|CLEAN-ARM-ENABLED)$' "$EV/tracer-result.txt" 2>/dev/null || chk_fail "tracer-result.txt has no token line"
  grep -q '^build: [0-9a-f]\{40\}' "$EV/precheck.txt" 2>/dev/null || chk_fail "precheck.txt has no build sha"
  grep -q '^backup .*_backup-pre-gap-uat04-' "$EV/precheck.txt" 2>/dev/null || chk_fail "precheck.txt has no backup path"
  for l in a b; do
    if [ -s "$EV/tracer-registry-$l.json" ] && [ -n "$id" ]; then
      jq -e 'type == "array"' "$EV/tracer-registry-$l.json" >/dev/null 2>&1 || chk_fail "tracer-registry-$l.json is not a registry projection"
      grep -q "^ha-$l: mqtt rows with unique id ISO_CLEAN_ID: [0-9]*, disabled_by:" "$EV/tracer-result.txt" || chk_fail "no result row for ha-$l"
    fi
  done
  [ "$(awk '{print $2}' "$EV/tracer-topics.txt" 2>/dev/null | head -n1)" = 1 ] || chk_fail "the retained export payload was not read back as retained"
  grep -q '^retain flag: 1$' "$EV/tracer-topics.txt" 2>/dev/null || chk_fail "no retained shape read-back in tracer-topics.txt"
  [ -z "$(sed -n '/^== /!p' "$EV/tracer-topics-after-off.txt" 2>/dev/null | sed '/^$/d')" ] || chk_fail "the export topics were not empty after the export was switched off"
  for g in "check-uat02.sh clean" "check-uat04.sh clean" "check-preflight.sh --quick"; do
    grep -qF "[tracer] $g PASS" "$EV/cleanup.txt" 2>/dev/null || chk_fail "cleanup.txt does not record PASS for '$g' (tracer)"
  done
  ! grep -q '^\[tracer\].* FAIL' "$EV/cleanup.txt" 2>/dev/null || chk_fail "cleanup.txt records a FAIL line (tracer)"
  n=$(grep -c -F "$id" "$EV/fixtures.txt" 2>/dev/null || true)
  [ "${n:-0}" -ge 1 ] || chk_fail "fixtures.txt does not name the fresh id"
  chk_finish "check-uat04-iso verify --tracer" "$EV"
}

case "$MODE" in
  tracer) do_tracer ;;
  verify)
    case "$ARG" in
      --tracer)
        do_verify_tracer
        exit $?
        ;;
      *)
        echo "ABORT verify without --tracer is added in plan 08-11 task 2" >&2
        exit 2
        ;;
    esac
    ;;
  *)
    echo "usage: check-uat04-iso.sh tracer | verify [--tracer]" >&2
    exit 2
    ;;
esac
