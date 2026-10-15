#!/usr/bin/env bash
# shellcheck disable=SC2001,SC2015,SC2016 # jq filters are single-quoted on purpose; `A && B || die` exits in die
# CR-01 release gate (plan 09.2-08, D-15, D-16). A pass/fail gate on exactly FIX: three variants on real instances,
# judged by the expectations in cr01-gate/expectations.txt, which were committed with this script before the first
# variant ran. Derived from the git-tracked 09.1-evidence/fix2/cr01-observation/observe-cr01.sh.
#
#   cr01-gate.sh gate
#   cr01-gate.sh pre V | payload V | publish V | rename V LETTER... | heartbeats V before|after
#   cr01-gate.sh restart V LETTER... | record V | outcome V
#   cr01-gate.sh verdict
#
# V is the variant: 3 (v3-positive-control), 2 (v2-reverse) or 1 (v1-bench-case). LETTER is a or b; ha-c is never
# touched. Run from the repository root under ~/ha-test/phase9.2.env with CR01_STATE set to a directory outside the
# repository (working files: payload, config document, rename record, timestamps). Exit codes: 0 done, 1 failed step,
# 2 ABORT (a precondition failed or the bench is not ready: never a verdict).
#
# Holds no secret: broker passwords and tokens are read by lib.sh and ha-test-guard from their 0600 files. Registry
# changes go through the WebSocket API only (ha-test-guard). Evidence holds fixed-field projections only: registry rows
# as {id, entity_id, unique_id, platform, disabled_by, name}, devices as {identifiers, name}, the retained topic as flag,
# length and equality, heartbeats as {instance_id, kept_legacy}, log lines as timestamp and fixed text.
set -uo pipefail
HT="$HOME/ha-test"
# shellcheck source=/dev/null
. "$HT/bin/lib.sh"
GUARD="$HT/bin/ha-test-guard"
unset PHASE8_EV_SUFFIX

ID=11111111-aaaa-4aaa-8aaa-000000000001 # "Lampe Test", owned by ha-a, mirrored natively on ha-b
TOPIC="homeassistant/device/$ID/config"
NAME="CR-01 kept button"
BASE_TOPIC=mqtt_actions
SW_VERSION=0.1.0
SETTLE_SECONDS=90
RENAME_WAIT_SECONDS=40
HEARTBEAT_LISTEN_SECONDS=35
GATE_MAX_AGE_SECONDS=900
PROVENANCE="release gate (D-15); expectations fixed in 09.2-08-PLAN.md and cr01-gate/expectations.txt before the run"
PAT='Removed [0-9]* duplicate entities|Disabled [0-9]* duplicate entities|keeps its MQTT device|postponed|Kept the MQTT entities of [0-9]* native devices|could not clear the discovery|cannot announce'
UNWRAP='(if type == "object" and has("result") then .result else . end)'

die() {
  echo "ABORT $*" >&2
  exit 2
}
now() { date -u +%FT%TZ; }

# ---- working directory and paths ------------------------------------------------------------------------------------
TOP=$(git rev-parse --show-toplevel 2>/dev/null) || die "run from inside the repository checkout"
[ -n "${CR01_STATE:-}" ] || die "CR01_STATE is not set (a working directory outside the repository is required)"
S=$(realpath -m "$CR01_STATE") || die "cannot resolve CR01_STATE"
case "$S/" in "$(realpath "$TOP")/"*) die "CR01_STATE ($S) lies inside the repository" ;; esac
mkdir -p "$S" || die "cannot create CR01_STATE"
chmod 700 "$S"
E3=$(evidence_root) || die "no evidence root"
G="$E3/cr01-gate"
[ -d "$G" ] || die "$G does not exist"
FIX=$(sed -n 's/^fix_sha: //p' "$E3/release/push-readiness.txt" 2>/dev/null | head -n1)
[[ "$FIX" =~ ^[0-9a-f]{40}$ ]] || die "no fix_sha in release/push-readiness.txt"

folder() {
  case "$1" in
    3) echo v3-positive-control ;;
    2) echo v2-reverse ;;
    1) echo v1-bench-case ;;
    *) return 1 ;;
  esac
}
# variant V: sets V, O (variant evidence folder) and SV (variant working folder)
variant() {
  V=${1:-}
  local f
  f=$(folder "$V") || die "the variant must be 3, 2 or 1"
  O="$G/$f"
  SV="$S/v$V"
  mkdir -p "$O" "$SV"
}
letters_ok() {
  [ $# -ge 1 ] || die "no instance letter given"
  local l
  for l in "$@"; do
    case "$l" in a | b) ;; *) die "instance letter '$l' is not a or b (ha-c is never touched)" ;; esac
  done
}

# ---- bench helpers --------------------------------------------------------------------------------------------------
running() { [ "$(podman inspect "$1" --format '{{.State.Running}}' 2>/dev/null)" = true ]; }
started_at() { podman inspect "$1" --format '{{.State.StartedAt}}' 2>/dev/null | sed 's/ m=.*//'; }
stop_named() { # stop_named LETTER... : graceful stop of the named containers only
  local c=() l
  for l in "$@"; do c+=("ha-$l"); done
  podman stop -t 60 "${c[@]}" >/dev/null 2>&1
  for l in "$@"; do ! running "ha-$l" || die "ha-$l did not stop"; done
}
start_named() { # start_named LETTER... : start the named containers and wait until their HTTP port answers
  local c=() l
  for l in "$@"; do c+=("ha-$l"); done
  podman start "${c[@]}" >/dev/null 2>&1 || die "podman start ${c[*]} failed"
  for l in "$@"; do wait_http "$(inst_port "$l")" || die "ha-$l did not come up"; done
}
ws() { "$GUARD" "$1" ws raw "${@:2}" 2>/dev/null; }
# registry rows of ID on the running instance: platform mqtt with unique id ID or ID_test_*, platform mqtt_actions with
# unique id ID or ID_*; fixed fields only
rows() {
  local out
  out=$(ws "$1" config/entity_registry/list) || return 1
  jq -e -S --arg id "$ID" "$UNWRAP"' | if type != "array" then error("no list") else . end
    | [.[] | select((.platform == "mqtt" and (.unique_id == $id or (.unique_id | startswith($id + "_test_"))))
                 or (.platform == "mqtt_actions" and (.unique_id == $id or (.unique_id | startswith($id + "_")))))
       | {id, entity_id, unique_id, platform, disabled_by, name}] | sort_by(.platform, .unique_id)' <<<"$out"
}
# devices of the running instance that carry the legacy identifier ["mqtt", "mqtt_actions_ID"]
devices() {
  local out
  out=$(ws "$1" config/device_registry/list) || return 1
  jq -e -S --arg ident "mqtt_actions_$ID" "$UNWRAP"' | if type != "array" then error("no list") else . end
    | [.[] | select(any(.identifiers[]?; . == ["mqtt", $ident])) | {identifiers, name}]' <<<"$out"
}
# registry unique ids of ID or ID_test_* on platform mqtt_actions in the registry file (the A7 comparison)
native_ids() {
  reg_rows "$HT/$1/.storage/core.entity_registry" |
    jq -r --arg id "$ID" '[.[] | select(.platform == "mqtt_actions") | .unique_id
      | select(. == $id or startswith($id + "_test_"))] | sort | .[]'
}
# log_since LETTER SINCE : lines of the instance log written at or after SINCE (local time, "YYYY-MM-DD HH:MM:SS") that
# match PAT; timestamp and text only, ANSI codes stripped. Continuation lines follow the timestamp of their entry.
log_since() {
  sed 's/\x1b\[[0-9;]*m//g' "$HT/$1/home-assistant.log" 2>/dev/null |
    awk -v s="$2" '/^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}/ { keep = (substr($0, 1, 19) >= s) } keep' |
    grep -E "$PAT" | sed -E 's/^([0-9-]+ [0-9:.]+) [A-Z]+ \([^)]*\) \[[^]]*\] /\1 /' | cut -c1-400 || true
}
retained_device_topics() { probe_sub -t 'homeassistant/device/#' -F '%t' -W 3 2>/dev/null; }

case "${1:-}" in
  gate) # (a) the bench gate before a variant; writes $S/gate.txt, which the next pre step consumes
    fails=()
    out=$("$HT/bin/check-uat02.sh" clean 2>&1)
    rc=$?
    [ "$rc" -eq 0 ] || fails+=("check-uat02.sh clean did not PASS (exit $rc)")
    ret=$(retained_device_topics)
    [ -z "$ret" ] || fails+=("something is retained on homeassistant/device/#")
    avail=$(probe_sub -t "$BASE_TOPIC/v1/instances/+/availability" -F '%r %t %p' -W 3 2>/dev/null)
    online=$(awk '$1 == 1 && $3 == "online" {split($2, p, "/"); print p[4]}' <<<"$avail" | sort | tr '\n' ' ')
    expect=$(printf '%s\n' "$(inst_id a)" "$(inst_id b)" | sort | tr '\n' ' ')
    [ "$online" = "$expect" ] || fails+=("retained availability online is not exactly ha-a and ha-b")
    hc=$(podman inspect ha-c --format '{{.State.Running}}' 2>/dev/null)
    [ "$hc" = false ] || fails+=("ha-c is not stopped (running: ${hc:-unknown})")
    {
      echo "bench gate (a) of the CR-01 gate ($(now))"
      echo "check-uat02.sh clean (suffix unset): exit $rc"
      sed "s|$TOP/||" <<<"$out" | sed 's/^/  /'
      echo "retained on homeassistant/device/#: $(grep -c . <<<"$ret") topics"
      echo "retained availability on $BASE_TOPIC/v1/instances/+/availability (retained flag, instance id, payload):"
      awk '{split($2, p, "/"); print "  " $1 " " p[4] " " $3}' <<<"$avail"
      echo "online ids: ${online:-none}; expected (ha-a, ha-b): $expect"
      echo "ha-c running: ${hc:-unknown}"
      if [ "${#fails[@]}" -eq 0 ]; then
        echo "result: PASS"
      else
        printf 'reason: %s\n' "${fails[@]}"
        echo "result: ABORT"
      fi
    } >"$S/gate.txt"
    cat "$S/gate.txt"
    [ "${#fails[@]}" -eq 0 ] || die "bench gate failed"
    ;;

  pre) # (b) pre-variant copy of both registries with both stopped (0700, outside the repository); start; 90 s; quick gate
    variant "${2:-}"
    [ -s "$S/gate.txt" ] && grep -qx 'result: PASS' "$S/gate.txt" || die "no passing gate record: run the gate step first"
    age=$(($(date +%s) - $(stat -c %Y "$S/gate.txt")))
    [ "$age" -le "$GATE_MAX_AGE_SECONDS" ] || die "the gate record is older than $GATE_MAX_AGE_SECONDS s: run the gate step again"
    mv "$S/gate.txt" "$O/gate.txt"
    echo "$V" >"$S/current-variant"
    rm -f "$SV"/*
    ptr="${RESEED_BACKUP_POINTER:-$HT/.current-backup-phase9.2}"
    base=$(cat "$ptr" 2>/dev/null) || die "no 9.2 backup pointer at $ptr"
    [ -d "$base" ] || die "9.2 backup base does not exist"
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    dst="$base/cr01-v$V-pre-$stamp"
    since=$(date '+%F %T')
    stop_named a b
    (
      umask 077
      mkdir -p "$dst/a" "$dst/b"
      chmod 700 "$dst" "$dst/a" "$dst/b"
      for l in a b; do
        cp -p "$HT/$l/.storage/core.entity_registry" "$HT/$l/.storage/core.device_registry" "$dst/$l/" || exit 1
      done
    ) || die "pre-variant copy failed"
    echo "$dst" >"$SV/pre-copy-path"
    start_named a b
    sleep "$SETTLE_SECONDS"
    pp=0
    for l in a b; do pp=$((pp + $(log_since "$l" "$since" | grep -c 'postponed'))); done
    qout=$("$HT/bin/check-preflight.sh" --quick 2>&1)
    qrc=$?
    {
      echo "pre-variant copy of variant $V ($(now))"
      echo "copy: <9.2 backup base>/$(basename "$dst")/{a,b}/ (core.entity_registry, core.device_registry; mode 0700; both stopped)"
      echo "started: ha-a $(started_at ha-a), ha-b $(started_at ha-b); waited $SETTLE_SECONDS s"
      echo "postponed lines of this start: $pp"
      echo "check-preflight.sh --quick: exit $qrc"
      sed "s|$TOP/||" <<<"$qout" | sed 's/^/  /'
    } >"$O/pre.txt"
    cat "$O/pre.txt"
    [ "$pp" -eq 0 ] || die "a postponed line in the start after the pre-variant copy"
    [ "$qrc" -eq 0 ] || die "check-preflight.sh --quick did not PASS after the pre-variant start"
    ;;

  payload) # (c) the legacy payload of ID, built as build_payloads of check-uat02.sh does, with the A7 unique-id check
    variant "${2:-}"
    py="$(mount_root)/.venv/bin/python"
    [ -x "$py" ] || die "no .venv python at $py"
    owner=$(inst_id a)
    probe_sub -t "$BASE_TOPIC/v1/devices/$ID/config" -C 1 -W 5 -F '%p' >"$SV/$ID.doc" 2>/dev/null
    [ -s "$SV/$ID.doc" ] || die "no retained config document for $ID on the broker"
    (cd "$TOP" && "$py" - "$SV" "$owner" "$BASE_TOPIC" "$SW_VERSION" "$ID") <<'PY' || die "payload builder failed"
import json
import sys

from custom_components.mqtt_actions.discovery import build_discovery
from custom_components.mqtt_actions.document import parse_document

tmp, owner, base, sw, *ids = sys.argv[1:]
for device_id in ids:
    with open(f"{tmp}/{device_id}.doc", encoding="utf-8") as handle:
        parsed = parse_document(device_id, handle.read())
    payload = build_discovery(spec=parsed.spec, base_topic=base, instance_id=owner, sw_version=sw)
    with open(f"{tmp}/{device_id}.json", "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
PY
    bad=0
    pc="$O/payload-check.txt"
    {
      echo "CR-01 gate payload check (A7), variant $V: built with custom_components.mqtt_actions.discovery.build_discovery"
      echo "from the retained config document of $ID, instance_id=$owner, sw_version=$SW_VERSION, base_topic=$BASE_TOPIC"
      echo "date: $(now)"
      echo "build: $FIX"
      echo
    } >"$pc"
    ident=$(jq -r '.device.identifiers[0]' "$SV/$ID.json")
    if [ "$ident" = "mqtt_actions_$ID" ]; then
      echo "device identifier: $ident (expected mqtt_actions_$ID): yes" >>"$pc"
    else
      echo "device identifier: $ident (expected mqtt_actions_$ID): NO" >>"$pc"
      bad=1
    fi
    built=$(jq -r '[.components[] | select(has("unique_id")) | .unique_id] | sort | .[]' "$SV/$ID.json")
    {
      echo "topic: $TOPIC, device name: $(jq -r '.device.name' "$SV/$ID.json")"
      echo "built unique ids:"
      sed 's/^/  /' <<<"$built"
    } >>"$pc"
    for l in a b; do
      reg=$(native_ids "$l")
      {
        echo "registry of ha-$l (platform mqtt_actions, unique id = id or id_test_*):"
        sed 's/^/  /' <<<"$reg"
      } >>"$pc"
      if [ -n "$built" ] && [ "$built" = "$reg" ]; then
        echo "ha-$l: built unique ids equal the registry rows: yes" >>"$pc"
      else
        echo "ha-$l: built unique ids equal the registry rows: NO" >>"$pc"
        bad=1
      fi
    done
    if [ "$bad" -eq 0 ]; then
      echo "result: built payload matches the registry unique ids on ha-a and ha-b" >>"$pc"
    else
      echo "result: MISMATCH" >>"$pc"
    fi
    cat "$pc"
    [ "$bad" -eq 0 ] || die "A7 unique-id check: mismatch"
    ;;

  publish) # (d) live publish retained QoS 1 while both run, read back, 20 s; (e) shape check on each instance
    variant "${2:-}"
    [ -s "$SV/$ID.json" ] || die "no built payload: run the payload step first"
    running ha-a && running ha-b || die "both instances must run for the live publish"
    for l in a b; do
      rows "$l" >"$O/rows-before-$l.json" || die "row query on ha-$l failed"
    done
    probe_pub -r -q 1 -t "$TOPIC" -f "$SV/$ID.json" || die "publish to $TOPIC failed"
    back=$(probe_sub -t "$TOPIC" -C 1 -W 5 -F '%r %p' 2>/dev/null)
    [ -n "$back" ] || die "read-back of $TOPIC is empty"
    rflag=$(awk '{print $1}' <<<"$back")
    same=no
    [ "$(sed 's/^[^ ]* //' <<<"$back" | jq -S -c . 2>/dev/null)" = "$(jq -S -c . "$SV/$ID.json")" ] && same=yes
    {
      echo
      echo "live publish: $(now), retained QoS 1 on $TOPIC while ha-a and ha-b run"
      echo "read-back: retained flag $rflag, payload equals the built payload: $same"
    } >>"$O/payload-check.txt"
    [ "$rflag" = 1 ] && [ "$same" = yes ] || die "read-back is not retained or differs from the published payload"
    sleep 20
    bad=0
    : >"$O/shape.txt"
    for l in a b; do
      f="$O/rows-after-publish-$l.json"
      rows "$l" >"$f" || die "row query on ha-$l failed"
      sw=$(jq --arg id "$ID" '[.[] | select(.platform == "mqtt" and .unique_id == $id and .disabled_by == "integration")] | length' "$f")
      btn=$(jq '[.[] | select(.platform == "mqtt" and (.entity_id | startswith("button.")) and .disabled_by == null)] | length' "$f")
      ok=no
      [ "$sw" -ge 1 ] && [ "$btn" -ge 1 ] && ok=yes
      [ "$ok" = yes ] || bad=1
      echo "ha-$l ($(now)): platform-mqtt row with unique id ID and disabled_by integration: $sw; enabled platform-mqtt button rows of ID: $btn; expected shape: $ok" >>"$O/shape.txt"
    done
    cat "$O/shape.txt"
    [ "$bad" -eq 0 ] || die "the expected shape is missing after the publish"
    ;;

  rename) # rename on each named instance the enabled replayed button with the lowest unique id to NAME
    variant "${2:-}"
    shift 2
    letters_ok "$@"
    {
      echo "CR-01 gate rename, variant $V, through config/entity_registry/update (WebSocket API, as the UI does)"
      echo "date: $(now)"
      echo "name: $NAME"
      echo
    } >"$O/rename.txt"
    : >"$SV/renamed"
    for l in "$@"; do
      f="$O/rows-after-publish-$l.json"
      [ -s "$f" ] || die "no rows after the publish for ha-$l"
      btn=$(jq -r '[.[] | select(.platform == "mqtt" and (.entity_id | startswith("button.")) and .disabled_by == null)]
        | sort_by(.unique_id) | .[0].entity_id // empty' "$f")
      [ -n "$btn" ] || die "no enabled replayed button on ha-$l"
      uid=$(jq -r --arg e "$btn" '.[] | select(.entity_id == $e) | .unique_id' "$f")
      rid=$(jq -r --arg e "$btn" '.[] | select(.entity_id == $e) | .id' "$f")
      resp=$(ws "$l" config/entity_registry/update "$(jq -cn --arg e "$btn" --arg n "$NAME" '{entity_id: $e, name: $n}')")
      got=$(jq -c "$UNWRAP"' | .entity_entry // . | {entity_id, platform, name, disabled_by}' <<<"$resp" 2>/dev/null)
      echo "ha-$l: entity_id $btn, unique_id $uid, registry id $rid, returned ${got:-<no answer>}" >>"$O/rename.txt"
      [ "$(jq -r '.name // empty' <<<"${got:-null}" 2>/dev/null)" = "$NAME" ] || die "the rename on ha-$l did not return NAME"
      echo "$l $btn $uid $rid" >>"$SV/renamed"
    done
    date +%s >"$SV/renamed-at"
    cat "$O/rename.txt"
    ;;

  heartbeats) # 35 s of heartbeats, each payload reduced to {instance_id, kept_legacy}
    variant "${2:-}"
    label=${3:-}
    case "$label" in before | after) ;; *) die "the label must be before or after" ;; esac
    t0=$(now)
    out=$(probe_sub -t "$BASE_TOPIC/v1/instances/+/heartbeat" -W "$HEARTBEAT_LISTEN_SECONDS" -F '%p' 2>/dev/null)
    {
      echo "heartbeats on $BASE_TOPIC/v1/instances/+/heartbeat ($label), listened $HEARTBEAT_LISTEN_SECONDS s from $t0 to $(now)"
      echo "each payload reduced to {instance_id, kept_legacy}; ha-a is $(inst_id a), ha-b is $(inst_id b)"
      jq -c -R 'fromjson? | {instance_id, kept_legacy}' <<<"$out"
    } >"$O/heartbeats-$label.txt"
    cat "$O/heartbeats-$label.txt"
    ;;

  restart) # graceful restart of the named containers only, then wait_http and 90 s
    variant "${2:-}"
    shift 2
    letters_ok "$@"
    if [ -s "$SV/renamed-at" ]; then
      left=$((RENAME_WAIT_SECONDS - ($(date +%s) - $(cat "$SV/renamed-at"))))
      [ "$left" -gt 0 ] && sleep "$left"
    else
      sleep 10
    fi
    for l in a b; do
      rows "$l" >"$O/rows-before-start-$l.json" || die "row query on ha-$l failed"
    done
    before_a=$(started_at ha-a)
    before_b=$(started_at ha-b)
    since=$(date '+%F %T')
    echo "$since" >"$SV/since-local"
    t0=$(now)
    stop_named "$@"
    start_named "$@"
    t1=$(now)
    sleep "$SETTLE_SECONDS"
    {
      echo "restart of variant $V: graceful podman stop -t 60 and podman start of $(printf 'ha-%s ' "$@")only"
      echo "stop issued: $t0 (log time $since); ports answered: $t1; waited $SETTLE_SECONDS s until $(now)"
      echo "ha-a StartedAt before: $before_a; after: $(started_at ha-a); running: $(podman inspect ha-a --format '{{.State.Running}}')"
      echo "ha-b StartedAt before: $before_b; after: $(started_at ha-b); running: $(podman inspect ha-b --format '{{.State.Running}}')"
    } >"$O/restart.txt"
    cat "$O/restart.txt"
    for l in a b; do
      case " $* " in *" $l "*) continue ;; esac
      running "ha-$l" || die "ha-$l was to keep running and does not"
      b=$before_a
      [ "$l" = b ] && b=$before_b
      [ "$(started_at "ha-$l")" = "$b" ] || die "ha-$l was to keep running and was restarted"
    done
    ;;

  record) # rows, devices, retained topic, log lines of this start (and the state of the renamed row on ha-b, variant 2)
    variant "${2:-}"
    [ -s "$SV/since-local" ] || die "no restart recorded: run the restart step first"
    since=$(cat "$SV/since-local")
    for l in a b; do
      rows "$l" >"$O/rows-after-start-$l.json" || die "row query on ha-$l failed"
      devices "$l" >"$O/devices-after-start-$l.json" || die "device query on ha-$l failed"
    done
    back=$(probe_sub -t "$TOPIC" -C 1 -W 5 -F '%r %l %p' 2>/dev/null)
    same=no
    [ -n "$back" ] && [ "$(sed 's/^[^ ]* [^ ]* //' <<<"$back" | jq -S -c . 2>/dev/null)" = "$(jq -S -c . "$SV/$ID.json")" ] && same=yes
    {
      echo "retained read of $TOPIC after the start of variant $V ($(now))"
      if [ -n "$back" ]; then
        echo "retained payload present: yes (retained flag $(awk '{print $1}' <<<"$back"))"
        echo "length: $(awk '{print $2}' <<<"$back") bytes"
      else
        echo "retained payload present: no"
        echo "length: 0"
      fi
      echo "JSON equals the published payload: $same"
    } >"$O/retained.txt"
    for l in a b; do
      {
        echo "ha-$l, lines written at or after $since (local log time, the stop of the restart step; ha-a StartedAt $(started_at ha-a), ha-b StartedAt $(started_at ha-b)) matching the gate patterns (timestamp and text)"
        log_since "$l" "$since"
      } >"$O/log-$l.txt"
    done
    if [ "$V" = 2 ]; then
      ents=$(jq -c --arg n "$NAME" '[.[] | select(.name == $n) | .entity_id]' "$O/rows-after-start-b.json")
      st=$(ws b get_states) || die "get_states on ha-b failed"
      jq -S --argjson e "$ents" "$UNWRAP"' | [.[] | select(.entity_id as $x | $e | index($x)) | {entity_id, state}]' <<<"$st" \
        >"$O/states-b.json" || die "state projection on ha-b failed"
    fi
    cat "$O/retained.txt"
    echo "record done ($(now))"
    ;;

  outcome) # apply the fixed expectations of the variant mechanically to the recorded files
    variant "${2:-}"
    for f in retained.txt log-a.txt log-b.txt rows-before-start-a.json rows-before-start-b.json \
      rows-after-start-a.json rows-after-start-b.json devices-after-start-a.json devices-after-start-b.json; do
      [ -f "$O/$f" ] || die "$f is missing: record the variant first"
    done
    pp_a=$(grep -c 'postponed' "$O/log-a.txt")
    pp_b=$(grep -c 'postponed' "$O/log-b.txt")
    [ "$pp_a" -eq 0 ] && [ "$pp_b" -eq 0 ] || die "a postponed line in this start (ha-a $pp_a, ha-b $pp_b): not a verdict"
    if [ "$V" != 3 ]; then
      want="b"
      [ "$V" = 1 ] && want="a b"
      for l in $want; do
        grep -q "^$l " "$SV/renamed" 2>/dev/null || die "no rename recorded on ha-$l"
      done
    fi
    [ "$V" = 2 ] && { [ -f "$O/states-b.json" ] || die "states-b.json is missing"; }
    yn() { if [ "$1" -ge 1 ]; then echo yes; else echo no; fi; }
    # retained topic facts
    t_present=no
    grep -q '^retained payload present: yes' "$O/retained.txt" && t_present=yes
    t_len=$(sed -n 's/^length: \([0-9]*\).*/\1/p' "$O/retained.txt")
    t_equal=no
    grep -qx 'JSON equals the published payload: yes' "$O/retained.txt" && t_equal=yes
    t_absent=no
    [ "$t_present" = no ] && t_absent=yes
    t_same=no
    [ "$t_present" = yes ] && [ "${t_len:-0}" -gt 0 ] && [ "$t_equal" = yes ] && t_same=yes
    # per-instance counts
    q() { # q FILE [JQ FLAGS] FILTER
      local f=$1
      shift
      jq --arg id "$ID" --arg n "$NAME" "$@" "$f"
    }
    info() { # informational counts of the log lines of this start
      echo "Removed lines $(grep -c 'Removed [0-9]* duplicate entities' "$O/log-$1.txt"), Disabled lines $(grep -c 'Disabled [0-9]* duplicate entities' "$O/log-$1.txt"), keeps-its-MQTT-device lines $(grep -c 'keeps its MQTT device' "$O/log-$1.txt"), another-instance-keeps lines $(grep -c 'another instance keeps' "$O/log-$1.txt"), postponed lines $(grep -c 'postponed' "$O/log-$1.txt")"
    }
    # every platform-mqtt row of ID that was integration-disabled before the start, by registry id
    dis_ids() { jq -c '[.[] | select(.platform == "mqtt" and .disabled_by == "integration") | .id]' "$O/rows-before-start-$1.json"; }
    kept_all() { # kept_all LETTER STRICT : 1 when every such id still exists (STRICT=1: with disabled_by integration)
      jq --argjson ids "$(dis_ids "$1")" --arg strict "$2" \
        '[$ids[] as $i | [.[] | select(.id == $i and ($strict == "0" or .disabled_by == "integration"))] | length >= 1] | all | if . then 1 else 0 end' \
        "$O/rows-after-start-$1.json"
    }
    n_dis() { jq 'length' <<<"$(dis_ids "$1")"; }
    lines=()
    vv=holds
    case "$V" in
      3)
        for l in a b; do
          r=$(q "$O/rows-after-start-$l.json" '[.[] | select(.platform == "mqtt")] | length')
          d=$(jq 'length' "$O/devices-after-start-$l.json")
          f1=no
          [ "$r" -eq 0 ] && f1=yes
          f2=no
          [ "$d" -eq 0 ] && f2=yes
          v=holds
          [ "$f1" = yes ] && [ "$f2" = yes ] && [ "$t_absent" = yes ] || v=contradicts
          [ "$v" = holds ] || vv=contradicts
          lines+=("ha-$l: $v; no platform-mqtt row with unique id ID or ID_test_* $f1 ($r rows), no device with identifier [\"mqtt\", \"mqtt_actions_ID\"] $f2 ($d devices), TOPIC holds no retained payload $t_absent; after one start (restart of ha-a and ha-b together); $(info "$l")")
        done
        ;;
      2)
        a1=$(yn "$(q "$O/rows-after-start-a.json" '[.[] | select(.platform == "mqtt" and .unique_id == $id and .disabled_by == "integration")] | length')")
        a2=$(yn "$(kept_all a 0)")
        a4n=$(grep -c 'another instance keeps' "$O/log-a.txt")
        a4=$(yn "$a4n")
        v=holds
        [ "$a1" = yes ] && [ "$a2" = yes ] && [ "$t_same" = yes ] && [ "$a4" = yes ] || v=contradicts
        [ "$v" = holds ] || vv=contradicts
        lines+=("ha-a: $v; platform-mqtt row with unique id ID present with disabled_by integration $a1, every platform-mqtt row of ID integration-disabled before the start still present by registry id $a2 ($(n_dis a) rows before), TOPIC retained non-empty and JSON equal to the published payload $t_same (present $t_present, length ${t_len:-0}, equal $t_equal), log lines of this start with \"another instance keeps\" $a4 ($a4n); restarted alone; $(info a)")
        ent=$(q "$O/rows-after-start-b.json" -r '[.[] | select(.platform == "mqtt" and .name == $n and .disabled_by == null)] | .[0].entity_id // empty')
        b1=no
        [ -n "$ent" ] && b1=yes
        st=""
        [ -n "$ent" ] && st=$(jq -r --arg e "$ent" '[.[] | select(.entity_id == $e) | .state] | .[0] // empty' "$O/states-b.json")
        b2=no
        [ -n "$st" ] && [ "$st" != unavailable ] && b2=yes
        b3=$(yn "$(q "$O/rows-after-start-b.json" '[.[] | select(.platform == "mqtt" and .unique_id == $id and .disabled_by == "integration")] | length')")
        v=holds
        [ "$b1" = yes ] && [ "$b2" = yes ] && [ "$b3" = yes ] || v=contradicts
        [ "$v" = holds ] || vv=contradicts
        lines+=("ha-b: $v; platform-mqtt row named NAME with disabled_by null present $b1 (${ent:-none}), its state present and not unavailable $b2 (state ${st:-none}), platform-mqtt row with unique id ID present with disabled_by integration $b3; kept running; $(info b)")
        ;;
      1)
        a1=$(yn "$(q "$O/rows-after-start-a.json" '[.[] | select(.platform == "mqtt" and .name == $n and .disabled_by == null)] | length')")
        a2=$(yn "$(q "$O/rows-after-start-a.json" '[.[] | select(.platform == "mqtt" and .unique_id == $id and .disabled_by == "integration")] | length')")
        v=holds
        [ "$a1" = yes ] && [ "$a2" = yes ] && [ "$t_same" = yes ] || v=contradicts
        [ "$v" = holds ] || vv=contradicts
        lines+=("ha-a: $v; platform-mqtt row named NAME with disabled_by null present $a1, platform-mqtt row with unique id ID present with disabled_by integration $a2, TOPIC retained non-empty and JSON equal to the published payload $t_same (present $t_present, length ${t_len:-0}, equal $t_equal); $(info a)")
        bp=$(q "$O/rows-after-start-b.json" -r '[.[] | select((.platform == "mqtt" or .platform == "mqtt_actions") and .name == $n and .disabled_by == null) | .platform] | unique | join(",")')
        b1=no
        [ -n "$bp" ] && b1=yes
        b2k=$(kept_all b 1)
        tw=$(q "$O/rows-after-start-b.json" '[.[] | select(.platform == "mqtt" and .unique_id == $id and .disabled_by == "integration")] | length')
        b2=no
        [ "$b2k" -eq 1 ] && [ "$tw" -ge 1 ] && b2=yes
        v=holds
        [ "$b1" = yes ] && [ "$b2" = yes ] && [ "$t_same" = yes ] || v=contradicts
        [ "$v" = holds ] || vv=contradicts
        lines+=("ha-b: $v; row named NAME with disabled_by null present on platform mqtt_actions or mqtt $b1 (${bp:-none}), every platform-mqtt row of ID integration-disabled before the start still present with disabled_by integration $b2 ($(n_dis b) rows before; switch twin with unique id ID present with disabled_by integration $(yn "$tw")), TOPIC holds the same retained payload $t_same; a Removed line is allowed (enabled replay twins, D-05); $(info b)")
        ;;
    esac
    {
      echo "$vv"
      printf '%s\n' "${lines[@]}"
      echo "$PROVENANCE"
      echo "build: $FIX"
    } >"$O/outcome.txt"
    cat "$O/outcome.txt"
    ;;

  verdict) # the overall gate verdict: holds only when all three variants hold
    overall=holds
    res=()
    for f in v3-positive-control v2-reverse v1-bench-case; do
      v=not-run
      [ -s "$G/$f/outcome.txt" ] && v=$(head -n1 "$G/$f/outcome.txt")
      [ "$v" = holds ] || overall=contradicts
      res+=("$f: $v")
    done
    {
      echo "$overall"
      printf '%s\n' "${res[@]}"
      echo "$PROVENANCE"
      echo "build: $FIX"
    } >"$G/verdict.txt"
    cat "$G/verdict.txt"
    ;;

  *)
    echo "usage: cr01-gate.sh gate | pre V | payload V | publish V | rename V LETTER... | heartbeats V before|after" >&2
    echo "                    | restart V LETTER... | record V | outcome V | verdict      (V: 3, 2 or 1; LETTER: a or b)" >&2
    exit 2
    ;;
esac
