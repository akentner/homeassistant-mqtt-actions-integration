#!/usr/bin/env bash
# UAT-02 (MIG-05 outside the test harness): a retained legacy Discovery replay at start leaves no `_2` duplicate behind the
# takeover on ha-a and ha-b. Phase 8, plan 08-02.
#   check-uat02.sh run     two startup rounds on both instances, then clean the broker topics; writes verdict.txt
#   check-uat02.sh live    observation only: legacy Discovery published while the instances run (no pass or fail)
#   check-uat02.sh clean   assert the bench is back at the baseline (registries, broker topics)
# Run from inside the checkout that holds the evidence. Exit: 0 PASS, 1 FAIL, 2 ABORT (bench problem, never a UAT result).
#
# THE EXPECTED VALUES ARE CODED HERE, BEFORE ANYTHING IS OBSERVED (D-08), so the verdict cannot be argued afterwards:
#   after a startup round, on BOTH instances
#     E1  zero registry rows with platform `mqtt`            (the baseline holds none)
#     E2  zero entity ids ending in `_2`                      (any platform)
#     E3  zero devices with identifier (mqtt, mqtt_actions_<migrated id>)
#     E4  the rows with platform `mqtt_actions` (entity_id, registry id, unique_id, device_id) equal the baseline
#   PASS only when E1 to E4 hold for both rounds on both instances. FAIL names round, instance and row. ABORT when the bench
#   is wrong (precondition, payload check, retained read-back).
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"

# ---- coded expectations ---------------------------------------------------------------------------------------------
ID_SWITCH=11111111-aaaa-4aaa-8aaa-000000000001 # "Lampe Test", owner ha-a, mirrored natively on ha-b
ID_SELECT=b6bd2c0e-6d81-49ea-8025-4bd087bd718a # "Bar Select", owner ha-a, mirrored natively on ha-b
MIGRATED=("$ID_SWITCH" "$ID_SELECT")
IDS_JSON=$(printf '%s\n' "${MIGRATED[@]}" | jq -R . | jq -sc .)
OWNER_ID=$(inst_id a)
BASE_TOPIC=mqtt_actions
SW_VERSION=0.1.0
SETTLE_SECONDS=90 # HA startup plus the 5.0 s quiet period of the catch (REPLAY_QUIET_SECONDS), with margin
LETTERS=(a b)

EV="$(evidence_root)/uat-02${PHASE8_EV_SUFFIX:-}"
SNAP="$HT/_snap-pre-live"
TMPD=$(mktemp -d)
trap 'rm -rf "$TMPD"' EXIT

mkdir -p "$EV"
RES=() # result lines: "PASS|FAIL|INFO name :: observed"
res() { RES+=("$1 $2 :: $3"); }
ABORT_MSG=""
abort() {
  ABORT_MSG="$1"
  echo "ABORT $1" >&2
  # only the run mode owns verdict.txt; an abort of live or clean must not overwrite a recorded PASS or FAIL
  [ "${1+x}" ] && [ "${MODE:-}" = run ] && verdict "$EV" ABORT "$1"
  exit 2
}

# ---- helpers ----------------------------------------------------------------------------------------------------------
running() { [ "$(podman inspect "$1" --format '{{.State.Running}}' 2>/dev/null)" = true ]; }
both_running() { running ha-a && running ha-b; }
both_stopped() { ! running ha-a && ! running ha-b; }
started_at() { podman inspect "$1" --format '{{.State.StartedAt}}' 2>/dev/null | sed -e 's/ m=.*//'; }
stop_both() {
  podman stop -t 60 ha-a ha-b >/dev/null 2>&1
  both_stopped || abort "ha-a and ha-b did not stop"
}
start_both() {
  podman start ha-a ha-b >/dev/null 2>&1 || abort "podman start failed"
  wait_http 8123 && wait_http 8124 || abort "an instance did not come up"
}
topic_of() { echo "homeassistant/device/$1/config"; }

# my own content-based precondition: the two instances and the broker are Up, the mounted custom_components is byte-identical
# to the tree of HEAD, and HEAD carries the custom_components tree of the pinned sha of 00-preflight/build.txt
precheck() {
  local rec t_rec t_head diffs l c
  for c in ha-a ha-b mosq; do running "$c" || return 1; done
  pin || return 1
  rec=$(sed -n 's/^sha: //p' "$(evidence_root)/00-preflight/build.txt" | head -n1)
  t_rec=$(git rev-parse "$rec:custom_components" 2>/dev/null) || return 1
  t_head=$(git rev-parse "$PIN_SHA:custom_components" 2>/dev/null) || return 1
  [ "$t_rec" = "$t_head" ] || {
    echo "custom_components tree of $rec differs from HEAD $PIN_SHA"
    return 1
  }
  diffs=$(mount_clean) || {
    echo "mount not clean: $diffs"
    return 1
  }
  for l in a b; do
    local f h k
    for f in manager.py takeover.py const.py document.py; do
      read -r h k < <(mount_hashes "$l" "$f")
      { [ -n "$h" ] && [ "$h" = "$k" ]; } || {
        echo "$l $f host/container sha256 differ"
        return 1
      }
    done
  done
  echo "pinned sha: $rec; HEAD: $PIN_SHA; custom_components tree identical: $t_head; mount byte-identical; hashes equal"
}

# ---- registry evaluation ----------------------------------------------------------------------------------------------
native_rows() { reg_rows "$HT/$1/.storage/core.entity_registry" | jq -S '[.[] | select(.platform == "mqtt_actions")]'; }
snapshot_baseline() { # snapshot_baseline LETTER OUTFILE STARTED_AT
  local l=$1 out=$2 started=$3 dir
  dir=$(inst_dir "$l")
  jq -n --arg inst "ha-$l" --arg started "$started" \
    --argjson native "$(native_rows "$l")" \
    --argjson all "$(reg_rows "$dir/.storage/core.entity_registry")" \
    --argjson mqttdev "$(mqtt_devices "$l")" \
    '{instance: $inst, started_at_before_stop: $started, native_rows: $native, mqtt_rows: [$all[] | select(.platform == "mqtt")],
      underscore2_rows: [$all[] | select(.entity_id | test("_2$"))], mqtt_devices: $mqttdev}' >"$out"
}
mqtt_devices() { # devices of the legacy discovery of the two migrated ids
  jq -c --argjson ids "$IDS_JSON" '[.data.devices[]
      | select(any(.identifiers[]; .[0] == "mqtt" and (.[1] as $x | any($ids[]; "mqtt_actions_" + . == $x))))
      | {id, identifiers, name}]' "$HT/$1/.storage/core.device_registry"
}
# eval_round LETTER ROUND BASELINE OUT : writes OUT, appends result lines
eval_round() {
  local l=$1 round=$2 base=$3 out=$4 all native mqtt dup mdev eq
  all=$(reg_rows "$HT/$l/.storage/core.entity_registry")
  native=$(native_rows "$l")
  mqtt=$(jq '[.[] | select(.platform == "mqtt")]' <<<"$all")
  dup=$(jq '[.[] | select(.entity_id | test("_2$"))]' <<<"$all")
  mdev=$(mqtt_devices "$l")
  [ "$native" = "$(jq -S '.native_rows' "$base")" ] && eq=true || eq=false
  jq -n --arg inst "ha-$l" --arg round "$round" --argjson native "$native" --argjson mqtt "$mqtt" --argjson dup "$dup" \
    --argjson mdev "$mdev" --argjson eq "$eq" --argjson base "$(jq -S '.native_rows' "$base")" \
    '{instance: $inst, round: $round, mqtt_rows: $mqtt, underscore2_rows: $dup, mqtt_devices: $mdev,
      native_rows_equal_baseline: $eq, native_rows: $native, baseline_native_rows: $base}' >"$out"
  local tag="round $round ha-$l"
  [ "$(jq length <<<"$mqtt")" -eq 0 ] && res PASS "E1 $tag" "no row with platform mqtt" ||
    res FAIL "E1 $tag" "platform mqtt rows: $(jq -c '[.[] | {entity_id, unique_id}]' <<<"$mqtt")"
  [ "$(jq length <<<"$dup")" -eq 0 ] && res PASS "E2 $tag" "no entity id ending in _2" ||
    res FAIL "E2 $tag" "_2 rows: $(jq -c '[.[] | .entity_id]' <<<"$dup")"
  [ "$(jq length <<<"$mdev")" -eq 0 ] && res PASS "E3 $tag" "no mqtt device mqtt_actions_<id>" ||
    res FAIL "E3 $tag" "legacy devices: $(jq -c '[.[] | .identifiers]' <<<"$mdev")"
  if [ "$eq" = true ]; then
    res PASS "E4 $tag" "$(jq length <<<"$native") mqtt_actions rows identical to the baseline"
  else
    res FAIL "E4 $tag" "differing rows: $(diff <(jq -c '.[]' <<<"$native") <(jq -S -c '.native_rows[]' "$base") | grep '^[<>]' | cut -c1-200 | tr '\n' ';')"
  fi
}

# ---- legacy payloads --------------------------------------------------------------------------------------------------
# Built by the repository's own build_discovery from the retained config document of each device (parsed with its own
# parse_document), never typed by hand. Run under the .venv of the mount-source checkout; the code is the tree proven
# identical by precheck.
build_payloads() { # writes $TMPD/<id>.json and $EV/legacy-payload-check.txt
  local py top id doc
  py="$(mount_root)/.venv/bin/python"
  [ -x "$py" ] || abort "no .venv python at $py"
  top=$(git rev-parse --show-toplevel)
  for id in "${MIGRATED[@]}"; do
    doc="$TMPD/$id.doc"
    probe_sub -t "$BASE_TOPIC/v1/devices/$id/config" -C 1 -W 5 -F '%p' >"$doc" 2>/dev/null
    [ -s "$doc" ] || abort "no retained config document for $id on the broker"
  done
  (cd "$top" && "$py" - "$TMPD" "$OWNER_ID" "$BASE_TOPIC" "$SW_VERSION" "${MIGRATED[@]}") <<'PY' || abort "payload builder failed"
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
  {
    echo "legacy payload check (A7): built with custom_components.mqtt_actions.discovery.build_discovery from the retained"
    echo "config documents, instance_id=$OWNER_ID, sw_version=$SW_VERSION"
    echo
  } >"$EV/legacy-payload-check.txt"
  local l built reg bad=0
  for id in "${MIGRATED[@]}"; do
    [ "$(jq -r '.device.identifiers[0]' "$TMPD/$id.json")" = "mqtt_actions_$id" ] || {
      echo "device identifier of $id is not mqtt_actions_$id" >>"$EV/legacy-payload-check.txt"
      bad=1
    }
    built=$(jq -r '[.components[] | select(has("unique_id")) | .unique_id] | sort | .[]' "$TMPD/$id.json")
    {
      echo "device $id: topic $(topic_of "$id"), device name $(jq -r '.device.name' "$TMPD/$id.json")"
      echo "  built unique ids:"
      sed 's/^/    /' <<<"$built"
    } >>"$EV/legacy-payload-check.txt"
    for l in "${LETTERS[@]}"; do
      # the registry's rows for this device that a legacy discovery could have created: the id itself and {id}_test_*
      reg=$(jq -r --arg id "$id" '[.[] | .unique_id | select(. == $id or startswith($id + "_test_"))] | sort | .[]' \
        <<<"$(native_rows "$l")")
      {
        echo "  registry of ha-$l (platform mqtt_actions, unique id = id or id_test_*):"
        sed 's/^/    /' <<<"$reg"
      } >>"$EV/legacy-payload-check.txt"
      if [ "$built" = "$reg" ]; then
        echo "  ha-$l: built unique ids equal the registry rows: yes" >>"$EV/legacy-payload-check.txt"
      else
        echo "  ha-$l: built unique ids equal the registry rows: NO" >>"$EV/legacy-payload-check.txt"
        bad=1
      fi
    done
  done
  [ "$bad" -eq 0 ] || abort "the built legacy payload does not match the registry unique ids (A7), see legacy-payload-check.txt"
  echo "result: built payloads match the registry unique ids on ha-a and ha-b" >>"$EV/legacy-payload-check.txt"
}

# publish_legacy LABEL : both instances must be stopped; publish retained QoS 1 and read back with a second subscription
publish_legacy() {
  local label=$1 id topic back
  both_stopped || abort "publish_legacy: an instance is running (a live publish is not the startup replay)"
  {
    echo "== $label: publish while ha-a and ha-b are stopped =="
  } >>"$EV/retained-topics.txt"
  for id in "${MIGRATED[@]}"; do
    topic=$(topic_of "$id")
    probe_pub -r -q 1 -t "$topic" -f "$TMPD/$id.json" || abort "publish to $topic failed"
    back=$(probe_sub -t "$topic" -C 1 -W 5 -F '%t %r %q %p' 2>/dev/null)
    [ -n "$back" ] || abort "read-back of $topic is empty: the publish was dropped (ACL silence?)"
    echo "$back" >>"$EV/retained-topics.txt"
    [ "$(sed 's/^[^ ]* [^ ]* [^ ]* //' <<<"$back" | jq -S -c .)" = "$(jq -S -c . "$TMPD/$id.json")" ] ||
      abort "read-back of $topic differs from the published payload"
    [ "$(awk '{print $2}' <<<"$back")" = 1 ] || abort "read-back of $topic is not retained"
  done
}
retained_state() { # retained_state LABEL : append which legacy topics exist now (3 s listen)
  local label=$1 out
  out=$(probe_sub -t 'homeassistant/device/#' -F '%t %r' -W 3 2>/dev/null)
  {
    echo "== $label: retained homeassistant/device/# =="
    if [ -n "$out" ]; then echo "$out"; else echo "(none)"; fi
  } >>"$EV/retained-topics.txt"
  [ -n "$out" ]
}
clear_legacy() {
  local id topic
  for id in "${MIGRATED[@]}"; do
    topic=$(topic_of "$id")
    probe_pub -r -q 1 -t "$topic" -n || abort "clearing $topic failed"
  done
  sleep 1
  [ -z "$(probe_sub -t 'homeassistant/device/#' -F '%t %r' -W 3 2>/dev/null)" ] ||
    abort "a legacy discovery topic is still retained after clearing it"
}

log_extract() { # log_extract LETTER HEADER : filtered lines of the instance log, before the next start rotates it
  local l=$1 hdr=$2 f="$HT/$1/home-assistant.log"
  {
    echo "== $hdr =="
    grep -E 'custom_components\.mqtt_actions|homeassistant\.components\.mqtt' "$f" 2>/dev/null | cut -c1-400 || true
  } >>"$EV/log-$l.txt"
}
info_line_count() { grep -c 'Removed [0-9]* duplicate entities that a replayed legacy discovery created' "$HT/$1/home-assistant.log" 2>/dev/null || true; }

# ---- mode: run --------------------------------------------------------------------------------------------------------
do_run() {
  local gate round l started_a started_b
  gate=$(precheck) || abort "content precondition failed: $gate"
  {
    echo "date: $(date -u +%FT%TZ)"
    echo "$gate"
    echo "StartedAt before the run: ha-a $(started_at ha-a), ha-b $(started_at ha-b)"
  } >"$EV/precheck.txt"
  : >"$EV/retained-topics.txt"
  : >"$EV/log-a.txt"
  : >"$EV/log-b.txt"

  # (0) the broker must start clean: any retained legacy topic would mean the baseline is not a baseline
  retained_state "before the run" && abort "a legacy discovery topic is retained before the run"

  # (1) stop both (flushes the registries) and take the baselines
  started_a=$(started_at ha-a)
  started_b=$(started_at ha-b)
  stop_both
  snapshot_baseline a "$EV/baseline-a.json" "$started_a"
  snapshot_baseline b "$EV/baseline-b.json" "$started_b"
  for l in "${LETTERS[@]}"; do
    [ "$(jq '.mqtt_rows | length' "$EV/baseline-$l.json")" -eq 0 ] || abort "baseline of ha-$l already holds mqtt rows"
    [ "$(jq '.underscore2_rows | length' "$EV/baseline-$l.json")" -eq 0 ] || abort "baseline of ha-$l already holds _2 rows"
    [ "$(jq '.mqtt_devices | length' "$EV/baseline-$l.json")" -eq 0 ] || abort "baseline of ha-$l already holds legacy devices"
    if [ "$(jq -S '.native_rows' "$EV/baseline-$l.json")" = "$(jq -S . "$(evidence_root)/00-preflight/registry-baseline-$l.json" | jq -S '[.[] | select(.platform == "mqtt_actions")]')" ]; then
      res INFO "baseline ha-$l" "equals the 00-preflight registry baseline"
    else
      res INFO "baseline ha-$l" "differs from the 00-preflight registry baseline (state moved since plan 08-01)"
    fi
  done

  # (2) payloads, with the A7 check before anything is published (needs the retained config documents: broker only)
  build_payloads

  for round in 1 2; do
    # (3) publish while both are stopped
    publish_legacy "round $round"
    # (4) start and let HA come up and the catch (5.0 s quiet period) run
    start_both
    sleep "$SETTLE_SECONDS"
    res INFO "log round $round ha-a" "INFO catch line count in the log so far: $(info_line_count a)"
    res INFO "log round $round ha-b" "INFO catch line count in the log so far: $(info_line_count b)"
    retained_state "round $round after the start" &&
      res INFO "retained round $round" "legacy topics still retained after the start" ||
      res INFO "retained round $round" "legacy topics gone after the start (core MQTT cleared them)"
    # (5) graceful stop flushes the registries; evaluate
    stop_both
    for l in "${LETTERS[@]}"; do
      log_extract "$l" "round $round (instance started $(started_at "ha-$l"))"
      eval_round "$l" "$round" "$EV/baseline-$l.json" "$EV/round$round-$l.json"
    done
  done

  # (7) clear the topics while stopped, read back empty, bring both up
  clear_legacy
  retained_state "after clearing" && abort "legacy topics still retained after clearing"
  start_both

  local fails
  fails=$(printf '%s\n' "${RES[@]}" | grep -c '^FAIL' || true)
  printf '%s\n' "${RES[@]}" >"$EV/result.txt"
  if [ "$fails" -eq 0 ]; then
    verdict "$EV" PASS "E1 to E4 hold in round 1 and round 2 on ha-a and ha-b" "build: $(sed -n 's/^sha: //p' "$(evidence_root)/00-preflight/build.txt" | head -n1)"
    echo "PASS UAT-02 $EV"
  else
    verdict "$EV" FAIL "$(printf '%s\n' "${RES[@]}" | grep '^FAIL' | head -n8)"
    echo "FAIL UAT-02: $fails assertion(s) failed, see $EV/result.txt"
    return 1
  fi
}

# ---- mode: live -------------------------------------------------------------------------------------------------------
live_rows() { # live_rows LETTER : rows platform mqtt or *_2 from the running instance through the guard (ids only)
  "$here/ha-test-guard" "$1" ws raw config/entity_registry/list 2>/dev/null |
    jq -c '(if type == "object" then .result else . end) | [.[]? | select(.platform == "mqtt" or (.entity_id | test("_2$"))) | {entity_id, platform, unique_id}]' 2>/dev/null
}
do_live() {
  local gate l out="$EV/live-variant.txt" id rows file_rows
  gate=$(precheck) || abort "content precondition failed: $gate"
  both_running || abort "live: both instances must run"
  retained_state "live: before" && abort "live: legacy topics are retained before the variant"
  rm -rf "$SNAP"
  mkdir -p "$SNAP"
  chmod 700 "$SNAP"
  for l in "${LETTERS[@]}"; do cp -a "$HT/$l/.storage" "$SNAP/$l-storage"; done
  {
    echo "live-republish variant (observation, no pass or fail of its own; Pitfall 3, deferred review item WR-03)"
    echo "date: $(date -u +%FT%TZ)"
    echo "snapshot of .storage taken to $SNAP (outside the repo; it holds credentials)"
    echo "build: $(sed -n 's/^sha: //p' "$(evidence_root)/00-preflight/build.txt" | head -n1)"
    echo
  } >"$out"
  build_payloads_live
  for id in "${MIGRATED[@]}"; do
    probe_pub -r -q 1 -t "$(topic_of "$id")" -f "$TMPD/$id.json" || abort "live publish failed"
  done
  echo "published both legacy payloads retained while ha-a and ha-b run ($(date -u +%T)Z)" >>"$out"
  sleep 20
  for l in "${LETTERS[@]}"; do
    rows=$(live_rows "$l")
    echo "T+20 s, ha-$l, rows with platform mqtt or entity id ending _2 (config/entity_registry/list): ${rows:-<no answer>}" >>"$out"
  done
  sleep 25
  for l in "${LETTERS[@]}"; do
    rows=$(live_rows "$l")
    echo "T+45 s, ha-$l, same query: ${rows:-<no answer>}" >>"$out"
  done
  # stop (flush), read the files, clear the topics while stopped, then the next start
  stop_both
  for l in "${LETTERS[@]}"; do
    file_rows=$(reg_rows "$HT/$l/.storage/core.entity_registry" | jq -c '[.[] | select(.platform == "mqtt" or (.entity_id | test("_2$"))) | {entity_id, platform, unique_id}]')
    echo "after the graceful stop, registry file of ha-$l, same rows: $file_rows" >>"$out"
    log_extract "$l" "live variant (instance started $(started_at "ha-$l"))"
  done
  clear_legacy
  echo "legacy topics cleared while the instances were stopped (read back empty)" >>"$out"
  start_both
  sleep "$SETTLE_SECONDS"
  stop_both
  for l in "${LETTERS[@]}"; do
    file_rows=$(reg_rows "$HT/$l/.storage/core.entity_registry" | jq -c '[.[] | select(.platform == "mqtt" or (.entity_id | test("_2$"))) | {entity_id, platform, unique_id}]')
    echo "after the next start and a graceful stop, registry file of ha-$l, same rows: $file_rows" >>"$out"
    log_extract "$l" "live variant, next start (instance started $(started_at "ha-$l"))"
    echo "ha-$l INFO catch line count in the log of the next start: $(info_line_count "$l")" >>"$out"
  done
  start_both
  echo "both instances started again ($(date -u +%T)Z)" >>"$out"
  echo "DONE live variant, see $out"
}
build_payloads_live() { # same builder, without rewriting legacy-payload-check.txt
  local keep="$EV/legacy-payload-check.txt" bak
  bak=$(mktemp)
  cp "$keep" "$bak" 2>/dev/null || true
  build_payloads
  cp "$bak" "$keep" 2>/dev/null || true
  rm -f "$bak"
}

# ---- mode: clean ------------------------------------------------------------------------------------------------------
do_clean() {
  local l base
  for l in "${LETTERS[@]}"; do
    base="$EV/baseline-$l.json"
    [ -s "$base" ] || {
      chk_fail "baseline-$l.json is missing"
      continue
    }
    local all native
    all=$(reg_rows "$HT/$l/.storage/core.entity_registry")
    native=$(native_rows "$l")
    # The "UAT Marker" fixture of plan 08-03 (MARKER_ID in .fixtures.env) is deliberate bench state added after the UAT-02
    # baseline was taken: its native rows (unique id = marker id or marker id + suffix) are excluded from this comparison only.
    local mid
    mid=$(sed -n 's/^MARKER_ID=//p' "$HT/.fixtures.env" 2>/dev/null | head -n1)
    native=$(jq -S --arg m "${mid:-__none__}" '[.[] | select((.unique_id | startswith($m)) | not)]' <<<"$native")
    # Hub-owned rows (unique id <hub entry id>_resync / _instance_mode / _roster) are bench state that moved with the hub:
    # plan 08-08 re-added the hub of ha-b under a new config entry id and instance id, so the baseline's hub rows are stale
    # by construction (bench defect, Rule 3, plan 08-11). Both sides are compared without them; E1 to E3 stay unchanged.
    local hubf='[.[] | select((.unique_id | test("_(resync|instance_mode|roster)$")) | not)]'
    native=$(jq -S "$hubf" <<<"$native")
    [ "$native" = "$(jq -S ".native_rows | $hubf" "$base")" ] || chk_fail "ha-$l: mqtt_actions rows (without hub rows) differ from the baseline"
    [ "$(jq '[.[] | select(.platform == "mqtt")] | length' <<<"$all")" -eq 0 ] || chk_fail "ha-$l: a row with platform mqtt exists"
    [ "$(jq '[.[] | select(.entity_id | test("_2$"))] | length' <<<"$all")" -eq 0 ] || chk_fail "ha-$l: an entity id ending in _2 exists"
    [ "$(mqtt_devices "$l" | jq length)" -eq 0 ] || chk_fail "ha-$l: a legacy mqtt device exists"
  done
  [ -z "$(probe_sub -t 'homeassistant/device/#' -F '%t' -W 3 2>/dev/null)" ] || chk_fail "a legacy discovery topic is still retained"
  both_running || chk_fail "ha-a and ha-b are not both running"
  chk_finish "UAT-02 clean" "$EV"
}

MODE=${1:-}
case "$MODE" in
  run) do_run ;;
  live) do_live ;;
  clean) do_clean ;;
  *)
    echo "usage: check-uat02.sh run | live | clean" >&2
    exit 2
    ;;
esac
