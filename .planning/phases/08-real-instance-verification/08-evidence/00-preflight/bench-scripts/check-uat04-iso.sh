#!/usr/bin/env bash
# Isolated reproduction of UAT-04 clause 2 (enabled mqtt-platform export duplicates on the core prefix). Phase 8, plan 08-11.
#   check-uat04-iso.sh tracer          the clean arm end to end for ONE fresh device (task 1); writes tracer-* evidence
#   check-uat04-iso.sh verify --tracer assert the tracer evidence is complete and the bench is back at its baseline
#   check-uat04-iso.sh run             both arms in one window, classification (task 2)
#   check-uat04-iso.sh verify          assert the full evidence, a valid classification and the baseline (task 2)
#   check-uat04-iso.sh disposition     print the validated owner option id of disposition.txt (task 3; exit 2 when invalid)
#   check-uat04-iso.sh applies TARGET  yes|no for guard, document, prune, repin, full-rerun, scoped (task 3; exit 2 when invalid)
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
# Full experiment (task 2). Two fresh device ids, exported in ONE window on the core prefix, both live registries read before
#   any restart: ISO-CLEAN (never had an mqtt-platform entity) and ISO-TWIN (a real deleted-entity tombstone left by a legacy
#   Discovery replay at start: retained legacy payload, instances started, replay catch removes the enabled legacy twin).
# Tombstone proof, read from the flushed (gracefully stopped) core.entity_registry files BEFORE the export, per instance:
#   T1 zero live rows with platform mqtt   T2 a deleted switch entity (platform mqtt, unique id ISO-TWIN) with disabled_by null
#   T3 no deleted mqtt-platform entity with unique id ISO-CLEAN (or ISO-CLEAN_*)
# Per arm and instance N = number of live mqtt rows with unique id equal to the arm's id, D = their disabled_by.
# Classification (first match wins; N != 1 in any of the four arm-instance cells is INCONCLUSIVE before any other rule):
#   CLEAN-FAILS      T3 holds on ha-a and ha-b, and ISO-CLEAN has D = null on at least one instance
#   TOMBSTONE-ONLY   T1, T2 and T3 hold on both instances, ISO-CLEAN has D = integration on both, ISO-TWIN has D = null on both
#   NOT-REPRODUCED   T1, T2 and T3 hold on both instances, and all four cells have D = integration
#   INCONCLUSIVE     every other combination (a failed proof, N != 1, a cell with another D, ha-a and ha-b disagreeing in an arm)
# P1 lines in result.txt: a FAIL line is the reproduction, not an abort. Hypothesis context lines (recorded, not rules): with
#   null tombstones Lampe Test and Bar Select are expected enabled (D = null), UAT Marker (tombstone integration) disabled.
# Fixture mirrors on ha-b are NOT approved: mirrors create their native entities on ha-b without an approval, and the replay
#   catch there finds the native twin without one.
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
  [ "$(sed -n 's/^header-sha256: //p' "$EV/tracer-result.txt" 2>/dev/null)" = "$(sha256sum "$EV/header-tracer.txt" 2>/dev/null | cut -d' ' -f1)" ] || chk_fail "the header sha256 of tracer-result.txt does not match header-tracer.txt"
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

# ---- mode: run (task 2) -----------------------------------------------------------------------------------------------------
TMPD=""
tomb_proj() { # tomb_proj FILE : deleted mqtt-platform entities of a (stopped instance's) registry file, fixed fields only
  local tmp
  tmp=$(mktemp)
  cp "$1" "$tmp"
  jq -S '[.data.deleted_entities[]? | select(.platform == "mqtt")
          | {entity_id, unique_id, disabled_by: (if has("disabled_by") then .disabled_by else "absent" end)}]
         | sort_by(.entity_id, .unique_id)' "$tmp"
  rm -f "$tmp"
}
live_mqtt_count() { # live_mqtt_count FILE : rows with platform mqtt in a registry file
  local tmp n
  tmp=$(mktemp)
  cp "$1" "$tmp"
  n=$(jq '[.data.entities[] | select(.platform == "mqtt")] | length' "$tmp")
  rm -f "$tmp"
  echo "$n"
}
tomb_state() { # tomb_state PROJFILE ID : none | present (disabled_by X[,Y])
  local d
  d=$(jq -r --arg id "$2" '[.[] | select(.unique_id == $id or (.unique_id | startswith($id + "_"))) | .disabled_by | tostring] | join(",")' "$1")
  if [ -z "$d" ]; then echo none; else echo "present (disabled_by $d)"; fi
}
# shape_read ID : read the retained export payload of one device from the core prefix; abort when the shape is wrong
shape_read() {
  local id=$1 line payload
  line=$(read_topics "$CORE_PREFIX/device/$id/config")
  [ -n "$line" ] || abort "no retained export payload on $CORE_PREFIX/device/$id/config after ${WAIT_APPLY} s"
  payload=${line#* * }
  {
    echo "$line" | cut -c1-200
    echo "retain flag: $(awk '{print $2}' <<<"$line")"
    echo "components (key, platform, enabled_by_default): $(jq -rc '[.components | to_entries[] | {key, platform: .value.platform, enabled_by_default: .value.enabled_by_default}]' <<<"$payload")"
  } >>"$EV/topics-core-prefix.txt"
  [ "$(awk '{print $2}' <<<"$line")" = 1 ] || abort "the export payload of $id is not retained"
  [ "$(jq -r '[.components[] | select((.platform != "switch") and (.platform != "select"))] | length' <<<"$payload")" = 0 ] || abort "a component of $id is neither switch nor select"
  [ "$(jq -r '[.components[] | select(.enabled_by_default != false)] | length' <<<"$payload")" = 0 ] || abort "a component of $id is not enabled_by_default false"
}
twin_round() { # twin_round CLEAN_ID TWIN_ID ; writes twin-round.txt and tombstones-before-{a,b}.json, sets T1/T2/T3 proof lines
  local clean=$1 twin=$2 top py doc built reg l topic back out n
  top=$(git rev-parse --show-toplevel)
  py="$(mount_root)/.venv/bin/python"
  [ -x "$py" ] || abort "no .venv python at $py"
  doc="$TMPD/$twin.doc"
  probe_sub -t "mqtt_actions/v1/devices/$twin/config" -C 1 -W 5 -F '%p' >"$doc" 2>/dev/null
  [ -s "$doc" ] || abort "no retained config document for $twin on the broker"
  (cd "$top" && "$py" - "$TMPD" "$(inst_id a)" mqtt_actions 0.1.0 "$twin") <<'PY' || abort "payload builder failed"
import json
import sys

from custom_components.mqtt_actions.discovery import build_discovery
from custom_components.mqtt_actions.document import parse_document

tmp, owner, base, sw, device_id = sys.argv[1:]
with open(f"{tmp}/{device_id}.doc", encoding="utf-8") as handle:
    parsed = parse_document(device_id, handle.read())
payload = build_discovery(spec=parsed.spec, base_topic=base, instance_id=owner, sw_version=sw)
with open(f"{tmp}/{device_id}.json", "w", encoding="utf-8") as handle:
    json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
PY
  {
    echo "twin round $(date -u +%FT%TZ): the field path of UAT-02 for ISO-TWIN $twin only"
    echo "legacy payload built with custom_components.mqtt_actions.discovery.build_discovery from the retained config document,"
    echo "instance_id=$(inst_id a) (ha-a), base topic mqtt_actions, sw_version 0.1.0"
  } >"$EV/twin-round.txt"
  [ "$(jq -r '.device.identifiers[0]' "$TMPD/$twin.json")" = "mqtt_actions_$twin" ] || abort "legacy device identifier of $twin is not mqtt_actions_$twin"
  built=$(jq -r '[.components[] | select(has("unique_id")) | .unique_id] | sort | .[]' "$TMPD/$twin.json")
  for l in a b; do
    reg=$(live_rows "$l" | jq -r --arg id "$twin" '[.[] | select(.platform == "mqtt_actions") | .unique_id | select(. == $id or startswith($id + "_test_"))] | sort | .[]')
    [ "$built" = "$reg" ] || abort "the built legacy unique ids differ from the registry rows of ha-$l (A7)"
  done
  echo "unique-id check (A7): the built legacy unique ids equal the native registry rows of ISO-TWIN on ha-a and ha-b: yes ($(wc -l <<<"$built") ids)" >>"$EV/twin-round.txt"

  stop_both
  topic="$CORE_PREFIX/device/$twin/config"
  probe_pub -r -q 1 -t "$topic" -f "$TMPD/$twin.json" || abort "publish of the legacy payload failed"
  back=$(probe_sub -t "$topic" -C 1 -W 5 -F '%t %r %q %p' 2>/dev/null)
  [ -n "$back" ] || abort "the legacy payload read-back is empty (ACL silence?)"
  [ "$(awk '{print $2}' <<<"$back")" = 1 ] || abort "the legacy payload is not retained"
  [ "$(sed 's/^[^ ]* [^ ]* [^ ]* //' <<<"$back" | jq -S -c .)" = "$(jq -S -c . "$TMPD/$twin.json")" ] || abort "the read-back differs from the published legacy payload"
  echo "legacy payload published retained QoS 1 on $topic while both instances were stopped, read back equal" >>"$EV/twin-round.txt"
  start_both
  sleep "$SETTLE_SECONDS"
  for l in a b; do
    n=$(grep -c 'Removed [0-9]* duplicate entities that a replayed legacy discovery created' "$HT/$l/home-assistant.log" 2>/dev/null || true)
    echo "ha-$l INFO catch line count in the log of this start: ${n:-0}" >>"$EV/twin-round.txt"
    grep 'Removed [0-9]* duplicate entities that a replayed legacy discovery created' "$HT/$l/home-assistant.log" 2>/dev/null | cut -c1-300 | sed "s/^/  ha-$l log: /" >>"$EV/twin-round.txt" || true
  done
  stop_both
  for l in a b; do
    tomb_proj "$HT/$l/.storage/core.entity_registry" >"$EV/tombstones-before-$l.json"
    out=$(live_mqtt_count "$HT/$l/.storage/core.entity_registry")
    [ "$out" = 0 ] && echo "proof T1 ha-$l PASS: zero live rows with platform mqtt (flushed registry file)" >>"$EV/twin-round.txt" ||
      echo "proof T1 ha-$l FAIL: $out live rows with platform mqtt" >>"$EV/twin-round.txt"
    out=$(jq -r --arg id "$twin" '[.[] | select(.entity_id | startswith("switch.")) | select(.unique_id == $id) | .disabled_by | tostring] | join(",")' "$EV/tombstones-before-$l.json")
    [ "$out" = null ] && echo "proof T2 ha-$l PASS: deleted switch entity with unique id ISO-TWIN, disabled_by null" >>"$EV/twin-round.txt" ||
      echo "proof T2 ha-$l FAIL: deleted switch entities with unique id ISO-TWIN have disabled_by '${out:-none}'" >>"$EV/twin-round.txt"
    out=$(tomb_state "$EV/tombstones-before-$l.json" "$clean")
    [ "$out" = none ] && echo "proof T3 ha-$l PASS: no deleted mqtt-platform entity for ISO-CLEAN" >>"$EV/twin-round.txt" ||
      echo "proof T3 ha-$l FAIL: ISO-CLEAN tombstone $out" >>"$EV/twin-round.txt"
  done
  probe_pub -r -q 1 -t "$topic" -n || abort "clearing $topic failed"
  sleep 1
  [ -z "$(probe_sub -t 'homeassistant/device/#' -F '%t' -W 3 2>/dev/null)" ] || abort "a legacy discovery topic is still retained after clearing it"
  echo "legacy topic cleared while both instances were stopped, read back empty" >>"$EV/twin-round.txt"
  start_both
  sleep 45
  "$here/check-preflight.sh" --quick >/dev/null || abort "check-preflight.sh --quick does not print PASS after the twin round"
  echo "both instances started again, check-preflight.sh --quick PASS" >>"$EV/twin-round.txt"
}

do_run() {
  local backup clean twin l k n d f token sha old
  declare -A N D
  mkdir -p "$EV"
  TMPD=$(mktemp -d)
  trap 'rm -rf "$TMPD"' EXIT
  sha=$(header_sha)
  header_block >"$EV/header.txt"
  need_baseline
  for f in twin-round.txt topics-core-prefix.txt topics-after-off.txt; do : >"$EV/$f"; done
  echo "== main run $(date -u +%FT%TZ)" >>"$EV/options-flow.txt"
  echo "== main run $(date -u +%FT%TZ)" >>"$EV/cleanup.txt"
  backup=$(backup_registries) || exit 2
  {
    echo "plan 08-11 task 2 (main run), $(date -u +%FT%TZ)"
    echo "build: $(sed -n 's/^sha: //p' "$(evidence_root)/00-preflight/build.txt" | head -n1)"
    echo "backup of both core.entity_registry files (outside the repo, mode 0700): $backup"
    echo "StartedAt after the gate start: ha-a $(started_at ha-a), ha-b $(started_at ha-b)"
  } >>"$EV/precheck.txt"

  clean=$(import_switch "UAT Iso Clean" "UAT04-ISO clean on" "UAT04-ISO clean off")
  twin=$(import_switch "UAT Iso Twin" "UAT04-ISO twin on" "UAT04-ISO twin off")
  old=$(fx_get ISO_CLEAN_ID)
  [ -n "$old" ] && fx_set TRACER_ISO_CLEAN_ID "$old"
  fx_set ISO_CLEAN_ID "$clean"
  fx_set ISO_TWIN_ID "$twin"
  wait_mirror "$clean" || abort "the mirror of $clean did not appear on ha-b within 60 s"
  wait_mirror "$twin" || abort "the mirror of $twin did not appear on ha-b within 60 s"
  n=$(cat "$backup/a/core.entity_registry" "$backup/b/core.entity_registry" | grep -c -F -e "$clean" -e "$twin" || true)
  {
    echo "== main run fixtures: UAT Iso Clean and UAT Iso Twin, switches, owner ha-a, actions system_log.write level warning"
    echo "ISO_CLEAN_ID=$clean"
    echo "ISO_TWIN_ID=$twin"
    echo "mirrors on ha-b: present, never approved"
    echo "occurrences of the two ids in the two backup registry files: $n"
  } >>"$EV/fixtures.txt"
  [ "$n" = 0 ] || abort "a fresh id occurs in a backup registry file ($n)"

  twin_round "$clean" "$twin"

  # the export window: both arms at once, no restart
  set_options a true "$CORE_PREFIX" "$EV/options-flow.txt"
  sleep "$WAIT_APPLY"
  echo "topics on $CORE_PREFIX/device/+/config (retained): $(read_topics "$CORE_PREFIX/device/+/config" | awk '{print $1}' | tr '\n' ' ')" >"$EV/topics-core-prefix.txt"
  shape_read "$clean"
  shape_read "$twin"
  for l in a b; do live_rows "$l" >"$EV/registry-core-prefix-$l.json"; done
  set_options a false "$EXPORT_PREFIX" "$EV/options-flow.txt"
  sleep "$WAIT_APPLY"
  {
    echo "== homeassistant/device/# (retained, 3 s)"
    read_topics 'homeassistant/device/#'
    echo "== mqtt_actions_export/# (retained, 3 s)"
    read_topics 'mqtt_actions_export/#'
    echo "== end"
  } >"$EV/topics-after-off.txt"
  [ -z "$(sed -n '/^== /!p' "$EV/topics-after-off.txt" | sed '/^$/d')" ] || echo "[main] export topics empty after off FAIL" >>"$EV/cleanup.txt"

  # evaluate
  for l in a b; do
    IFS=$'\t' read -r n d < <(rows_for "$l" "$clean" "$EV/registry-core-prefix-$l.json")
    N[clean-$l]=$n
    D[clean-$l]=${d:-none}
    IFS=$'\t' read -r n d < <(rows_for "$l" "$twin" "$EV/registry-core-prefix-$l.json")
    N[twin-$l]=$n
    D[twin-$l]=${d:-none}
  done
  {
    echo "INFO header-sha256 :: $sha"
    echo "INFO ISO_CLEAN_ID :: $clean"
    echo "INFO ISO_TWIN_ID :: $twin"
    for k in clean twin; do
      for l in a b; do
        if [ "${N[$k-$l]}" = 1 ] && [ "${D[$k-$l]}" = integration ]; then
          echo "PASS P1 ISO-${k^^} ha-$l :: one mqtt row, disabled_by integration"
        else
          echo "FAIL P1 ISO-${k^^} ha-$l :: mqtt rows ${N[$k-$l]}, disabled_by ${D[$k-$l]}"
        fi
      done
    done
    for l in a b; do
      for dev in "$ID_SWITCH:Lampe Test" "$ID_SELECT:Bar Select" "$ID_MARKER:UAT Marker"; do
        IFS=$'\t' read -r n d < <(rows_for "$l" "${dev%%:*}" "$EV/registry-core-prefix-$l.json")
        echo "INFO hypothesis ha-$l ${dev#*:} :: mqtt rows $n, disabled_by ${d:-none} (prediction: Lampe Test and Bar Select null, UAT Marker integration)"
      done
    done
    grep '^proof ' "$EV/twin-round.txt" | sed 's/^proof /INFO proof /'
  } >"$EV/result.txt"
  # classification, the rules coded in the header
  local allone=1 t3=1 proof=1 key
  for key in clean-a clean-b twin-a twin-b; do [ "${N[$key]}" = 1 ] || allone=0; done
  for l in a b; do grep -q "^proof T3 ha-$l PASS" "$EV/twin-round.txt" || t3=0; done
  grep -c '^proof T[123] ha-[ab] PASS' "$EV/twin-round.txt" | grep -qx 6 || proof=0
  if [ "$allone" = 0 ]; then
    token=INCONCLUSIVE
  elif [ "$t3" = 1 ] && { [ "${D[clean-a]}" = null ] || [ "${D[clean-b]}" = null ]; }; then
    token=CLEAN-FAILS
  elif [ "$proof" = 1 ] && [ "${D[clean-a]}" = integration ] && [ "${D[clean-b]}" = integration ] && [ "${D[twin-a]}" = null ] && [ "${D[twin-b]}" = null ]; then
    token=TOMBSTONE-ONLY
  elif [ "$proof" = 1 ] && [ "${D[clean-a]}" = integration ] && [ "${D[clean-b]}" = integration ] && [ "${D[twin-a]}" = integration ] && [ "${D[twin-b]}" = integration ]; then
    token=NOT-REPRODUCED
  else
    token=INCONCLUSIVE
  fi
  {
    echo "$token"
    for k in clean twin; do
      for l in a b; do
        echo "ISO-${k^^} ha-$l: mqtt rows ${N[$k-$l]}, disabled_by ${D[$k-$l]}, tombstone before the export: $(tomb_state "$EV/tombstones-before-$l.json" "$([ "$k" = clean ] && echo "$clean" || echo "$twin")")"
      done
    done
  } >"$EV/classification.txt"
  echo "INFO classification :: $token" >>"$EV/result.txt"

  cleanup_round main "$clean" "$twin"
  if "$here/check-stale-anchor.sh" >/dev/null 2>&1; then
    echo "[main] check-stale-anchor.sh PASS" >>"$EV/cleanup.txt"
  else
    echo "[main] check-stale-anchor.sh FAIL" >>"$EV/cleanup.txt"
  fi
  echo "main run done: $token (see $EV/classification.txt)"
}

# ---- mode: verify -----------------------------------------------------------------------------------------------------------
do_verify() {
  local f token l k g sha
  for f in precheck.txt fixtures.txt options-flow.txt header.txt twin-round.txt tombstones-before-a.json tombstones-before-b.json \
    topics-core-prefix.txt registry-core-prefix-a.json registry-core-prefix-b.json topics-after-off.txt result.txt classification.txt cleanup.txt; do
    [ -s "$EV/$f" ] || chk_fail "evidence file missing or empty: $f"
  done
  token=$(head -n1 "$EV/classification.txt" 2>/dev/null)
  case "$token" in
    TOMBSTONE-ONLY | CLEAN-FAILS | NOT-REPRODUCED) ;;
    INCONCLUSIVE) chk_fail "the classification is INCONCLUSIVE: it is never a basis for the decision, fix the cause and re-run task 2 from step 1" ;;
    *) chk_fail "classification.txt line 1 is not one of the four tokens ('$token')" ;;
  esac
  for k in CLEAN TWIN; do
    for l in a b; do
      grep -q "^ISO-$k ha-$l: mqtt rows [0-9]*, disabled_by .*, tombstone before the export: " "$EV/classification.txt" 2>/dev/null || chk_fail "classification.txt has no row for ISO-$k ha-$l"
    done
  done
  for l in a b; do
    grep -q "^proof T3 ha-$l PASS" "$EV/twin-round.txt" 2>/dev/null || chk_fail "tombstone proof T3 of ha-$l does not hold"
    if [ "$token" != CLEAN-FAILS ]; then
      grep -q "^proof T1 ha-$l PASS" "$EV/twin-round.txt" 2>/dev/null || chk_fail "tombstone proof T1 of ha-$l does not hold"
      grep -q "^proof T2 ha-$l PASS" "$EV/twin-round.txt" 2>/dev/null || chk_fail "tombstone proof T2 of ha-$l does not hold"
    fi
    grep -q "^ha-$l INFO catch line count in the log of this start: [0-9]" "$EV/twin-round.txt" 2>/dev/null || chk_fail "twin-round.txt has no catch line count of ha-$l"
    jq -e 'type == "array"' "$EV/registry-core-prefix-$l.json" >/dev/null 2>&1 || chk_fail "registry-core-prefix-$l.json is not a registry projection"
    jq -e 'type == "array"' "$EV/tombstones-before-$l.json" >/dev/null 2>&1 || chk_fail "tombstones-before-$l.json is not a projection"
  done
  sha=$(sed -n 's/^INFO header-sha256 :: //p' "$EV/result.txt" 2>/dev/null)
  [ -n "$sha" ] && [ "$sha" = "$(sha256sum "$EV/header.txt" 2>/dev/null | cut -d' ' -f1)" ] || chk_fail "the header sha256 of result.txt does not match header.txt"
  [ -z "$(sed -n '/^== /!p' "$EV/topics-after-off.txt" 2>/dev/null | sed '/^$/d')" ] || chk_fail "the export topics were not empty after the export was switched off"
  for g in "check-uat02.sh clean" "check-uat04.sh clean" "check-preflight.sh --quick" "check-stale-anchor.sh"; do
    grep -qF "[main] $g PASS" "$EV/cleanup.txt" 2>/dev/null || chk_fail "cleanup.txt does not record PASS for '$g' (main run)"
  done
  ! grep -q '^\[main\].* FAIL' "$EV/cleanup.txt" 2>/dev/null || chk_fail "cleanup.txt records a FAIL line (main run)"
  "$here/check-evidence-clean.sh" "$EV" >/dev/null 2>&1 || chk_fail "the evidence scan found a secret or failed"
  chk_finish "check-uat04-iso verify ($token)" "$EV"
}

# ---- owner disposition (task 3): fail closed, a missing or invalid file never reads as a decision ------------------------------
DISP_ID=""
DISP_MOD=""
DISP_WHY=""
# disp_load : validates $EV/disposition.txt, sets DISP_ID and DISP_MOD, returns 1 with DISP_WHY set when invalid
disp_load() {
  local f="$EV/disposition.txt" l2 l3
  DISP_ID=""
  DISP_MOD=""
  [ -s "$f" ] || {
    DISP_WHY="disposition.txt is missing or empty"
    return 1
  }
  DISP_ID=$(sed -n '1p' "$f")
  l2=$(sed -n '2p' "$f")
  l3=$(sed -n '3p' "$f")
  case "$DISP_ID" in
    guard | guard-and-document | document | bench-artifact) ;;
    *)
      DISP_WHY="line 1 is not one of guard, guard-and-document, document, bench-artifact"
      return 1
      ;;
  esac
  case "$l2" in
    "modifier: full-rerun") DISP_MOD=full-rerun ;;
    "modifier: scoped") DISP_MOD=scoped ;;
    "modifier: none") DISP_MOD=none ;;
    *)
      DISP_WHY="line 2 is not a valid modifier line"
      return 1
      ;;
  esac
  case "$DISP_ID" in
    guard | guard-and-document)
      [ "$l3" = "not-affected-confirmed: yes" ] || {
        DISP_WHY="a guard option lacks 'not-affected-confirmed: yes' on line 3"
        return 1
      }
      [ "$DISP_MOD" = full-rerun ] || [ "$DISP_MOD" = scoped ] || {
        DISP_WHY="a guard option needs the modifier full-rerun or scoped"
        return 1
      }
      ;;
    *)
      [ "$DISP_MOD" = none ] || {
        DISP_WHY="$DISP_ID carries a modifier other than none"
        return 1
      }
      [ "$l3" = "not-affected-confirmed: not-applicable" ] || {
        DISP_WHY="$DISP_ID needs 'not-affected-confirmed: not-applicable' on line 3"
        return 1
      }
      ;;
  esac
  return 0
}
do_disposition() {
  if ! disp_load; then
    sed -n '1p' "$EV/disposition.txt" 2>/dev/null
    echo "INVALID disposition: $DISP_WHY" >&2
    exit 2
  fi
  echo "$DISP_ID"
}
do_applies() {
  local target=$1 guard=no
  if ! disp_load; then
    echo "INVALID disposition: $DISP_WHY" >&2
    exit 2
  fi
  case "$DISP_ID" in guard | guard-and-document) guard=yes ;; esac
  case "$target" in
    guard | repin) echo "$guard" ;;
    document) case "$DISP_ID" in document | guard-and-document) echo yes ;; *) echo no ;; esac ;;
    prune) case "$DISP_ID" in document | bench-artifact) echo yes ;; *) echo no ;; esac ;;
    full-rerun) [ "$guard" = yes ] && [ "$DISP_MOD" = full-rerun ] && echo yes || echo no ;;
    scoped) [ "$guard" = yes ] && [ "$DISP_MOD" = scoped ] && echo yes || echo no ;;
    *)
      echo "INVALID target '$target': use guard, document, prune, repin, full-rerun or scoped" >&2
      exit 2
      ;;
  esac
}

case "$MODE" in
  tracer) do_tracer ;;
  run) do_run ;;
  verify)
    case "$ARG" in
      --tracer)
        do_verify_tracer
        exit $?
        ;;
      "")
        do_verify
        exit $?
        ;;
      *)
        echo "usage: check-uat04-iso.sh verify [--tracer]" >&2
        exit 2
        ;;
    esac
    ;;
  disposition) do_disposition ;;
  applies) do_applies "$ARG" ;;
  *)
    echo "usage: check-uat04-iso.sh tracer | run | verify [--tracer] | disposition | applies TARGET" >&2
    exit 2
    ;;
esac
