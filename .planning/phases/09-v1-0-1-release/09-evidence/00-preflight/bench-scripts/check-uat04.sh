#!/usr/bin/env bash
# UAT-04: the Discovery export is disabled by default and has no buttons, the core MQTT prefix yields only disabled duplicates,
# and switching the export off clears its topics. Phase 8, plan 08-04.
#   check-uat04.sh run     ACL rows, export on (default prefix), export on the core prefix, export off; writes the evidence
#                          folder and verdict.txt
#   check-uat04.sh clean   assert the export is off by the broker facts (no export topic, nothing retained on homeassistant/device)
# Run from inside the checkout that holds the evidence. Exit: 0 PASS, 1 FAIL, 2 ABORT (bench problem, never a UAT result).
#
# EXPECTED VALUES ARE CODED HERE, BEFORE ANYTHING IS OBSERVED (D-08).
#   Clause 1 (export on, default prefix mqtt_actions_export), read back by a second client (uat_probe):
#     X1  a retained payload exists on mqtt_actions_export/device/<id>/config for each owned native device
#         (Lampe Test, Bar Select, UAT Marker)
#     X2  every key under `components` has platform switch or select
#     X3  every component has enabled_by_default == false
#     X4  no component has platform button, no component key starts with test_, the payload text has no `/test` topic
#     X5  nothing is retained on homeassistant/device/+/config
#   Clause 2 (export prefix homeassistant, NO restart), ha-a AND ha-b entity registries read through the WebSocket API:
#     X6  the old export prefix holds no retained message; homeassistant/device/<id>/config holds the same shape (X1 to X4)
#     X7  per exported device exactly ONE row with platform mqtt, unique_id == device id, disabled_by == integration
#     X8  no enabled (disabled_by null) row with platform mqtt
#     X9  the native rows (platform mqtt_actions, unique_id == device id) are present and enabled
#   Clause 3 (export off):
#     X10 mqtt_actions_export/# and homeassistant/device/# hold no retained message (clear = empty retained payload)
#   Leftover disabled mqtt rows after the off step are an observation, not an assertion.
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"
G="$here/ha-test-guard"

MODE=${1:-}
case "$MODE" in run | clean) ;; *)
  echo "usage: check-uat04.sh run | clean" >&2
  exit 2
  ;;
esac

EV="$(evidence_root)/uat-04${PHASE8_EV_SUFFIX:-}"
ACL="$HT/mosquitto/acl"
ACL_BAK="$HT/mosquitto/acl.bak-phase8-04"
EXPORT_PREFIX=mqtt_actions_export
CORE_PREFIX=homeassistant
ACL_ROW="topic readwrite ${EXPORT_PREFIX}/#"
WAIT_APPLY=20

ID_SWITCH=11111111-aaaa-4aaa-8aaa-000000000001 # "Lampe Test"
ID_SELECT=b6bd2c0e-6d81-49ea-8025-4bd087bd718a # "Bar Select"
ID_MARKER=$(sed -n 's/^MARKER_ID=//p' "$HT/.fixtures.env" 2>/dev/null | head -n1)
DEVS=("$ID_SWITCH" "$ID_SELECT" "$ID_MARKER")

abort() {
  echo "ABORT $1" >&2
  [ "$MODE" = run ] && verdict "$EV" ABORT "$1"
  exit 2
}

# ---- mode: clean --------------------------------------------------------------------------------------------------------
if [ "$MODE" = clean ]; then
  [ -z "$(probe_sub -t "${EXPORT_PREFIX}/#" -F '%t' -W 3 2>/dev/null)" ] || chk_fail "a retained message remains under ${EXPORT_PREFIX}/"
  [ -z "$(probe_sub -t 'homeassistant/device/#' -F '%t' -W 3 2>/dev/null)" ] || chk_fail "a retained message remains under homeassistant/device/"
  chk_finish "UAT-04 clean" "$EV"
  exit $?
fi

# ---- helpers -----------------------------------------------------------------------------------------------------------------
mkdir -p "$EV"
RES=()
res() { RES+=("$1 $2 :: $3"); }

[ -n "$ID_MARKER" ] || abort "no MARKER_ID in .fixtures.env"
"$here/check-preflight.sh" --quick >/dev/null || abort "check-preflight.sh --quick does not print PASS"
"$here/check-marker.sh" approved >/dev/null || abort "check-marker.sh approved does not print PASS"
env -u PHASE8_EV_SUFFIX "$here/check-uat02.sh" clean >/dev/null || abort "check-uat02.sh clean does not print PASS"

# retained read of a topic filter: lines "topic retain payload" (a second client, T-08-03)
read_topics() { probe_sub -t "$1" -F '%t %r %p' -W 3 2>/dev/null; }

# hub config entry id of an instance (ids only)
entry_id() { "$G" "$1" ws raw config_entries/get | jq -r '[.result[] | select(.domain=="mqtt_actions") | .entry_id][0] // empty'; }

# set_options LETTER EXPORT(true|false) PREFIX ; runs the hub options flow through the REST endpoints
set_options() {
  local l=$1 on=$2 prefix=$3 eid start flow sub
  eid=$(entry_id "$l")
  [ -n "$eid" ] || abort "no mqtt_actions config entry on ha-$l"
  start=$("$G" "$l" rest POST /api/config/config_entries/options/flow "{\"handler\":\"$eid\"}")
  flow=$(jq -r '.flow_id // empty' <<<"$start" 2>/dev/null)
  [ -n "$flow" ] || abort "the options flow did not start (response keys: $(jq -rc 'keys' <<<"$start" 2>/dev/null))"
  sub=$("$G" "$l" rest POST "/api/config/config_entries/options/flow/$flow" \
    "{\"delete_devices_on_remove\":false,\"discovery_export\":$on,\"export_prefix\":\"$prefix\"}")
  echo "options flow ha-$l: discovery_export=$on export_prefix=$prefix -> type=$(jq -r '.type // "-"' <<<"$sub") errors=$(jq -c '.errors // {}' <<<"$sub")" >>"$EV/options-flow.txt"
  [ "$(jq -r '.type // empty' <<<"$sub")" = create_entry ] || abort "the options flow did not end in create_entry"
}

# shape_check LABEL PREFIX : asserts X1 to X4 for the topics under PREFIX/device/<id>/config; appends to export-shape-check.txt
shape_check() {
  local label=$1 prefix=$2 lines id line payload retain keys
  lines=$(read_topics "${prefix}/device/+/config")
  {
    echo "== $label (prefix $prefix)"
    echo "topics read back: $(awk 'NF{print $1}' <<<"$lines" | wc -l)"
  } >>"$EV/export-shape-check.txt"
  for id in "${DEVS[@]}"; do
    line=$(grep -F "${prefix}/device/${id}/config " <<<"$lines" | head -n1)
    if [ -z "$line" ]; then
      res FAIL "X1 $label $id" "no retained payload on ${prefix}/device/${id}/config"
      echo "device $id: NO RETAINED PAYLOAD" >>"$EV/export-shape-check.txt"
      continue
    fi
    retain=$(awk '{print $2}' <<<"$line")
    payload=${line#* * }
    [ "$retain" = 1 ] && res PASS "X1 $label $id" "retained payload present" || res FAIL "X1 $label $id" "payload not retained"
    keys=$(jq -rc '.components | to_entries | map({key, platform: .value.platform, enabled_by_default: .value.enabled_by_default})' <<<"$payload" 2>/dev/null)
    echo "device $id: name=$(jq -r '.device.name' <<<"$payload") components=$keys" >>"$EV/export-shape-check.txt"
    [ -n "$keys" ] || {
      res FAIL "X2 $label $id" "payload is not JSON with components"
      continue
    }
    bad=$(jq -r '[.components[] | select((.platform != "switch") and (.platform != "select"))] | length' <<<"$payload")
    [ "$bad" = 0 ] && res PASS "X2 $label $id" "components are only switch or select" || res FAIL "X2 $label $id" "$bad component(s) of another platform: $keys"
    bad=$(jq -r '[.components[] | select(.enabled_by_default != false)] | length' <<<"$payload")
    [ "$bad" = 0 ] && res PASS "X3 $label $id" "enabled_by_default false on every component" || res FAIL "X3 $label $id" "$bad component(s) without enabled_by_default false: $keys"
    bad=$(jq -r '[.components | to_entries[] | select(.value.platform == "button" or (.key | startswith("test_")))] | length' <<<"$payload")
    [ "$bad" = 0 ] && res PASS "X4 $label $id buttons" "no button, no test_ key" || res FAIL "X4 $label $id buttons" "button or test_ key present: $keys"
    if grep -q '/test' <<<"$payload"; then
      res FAIL "X4 $label $id test topic" "the payload mentions a /test topic"
    else
      res PASS "X4 $label $id test topic" "no /test topic in the payload"
    fi
  done
  echo "extra topics (not one of the three devices): $(awk 'NF{print $1}' <<<"$lines" | grep -v -e "/${DEVS[0]}/" -e "/${DEVS[1]}/" -e "/${DEVS[2]}/" | tr '\n' ' ')" >>"$EV/export-shape-check.txt"
  printf '%s\n' "$lines" >"$EV/$3"
}

# registry rows of a running instance (same selection as reg_rows, read through the API)
live_rows() {
  "$G" "$1" ws raw config/entity_registry/list | jq -S '[.result[]
      | if (.platform == "mqtt" or .platform == "mqtt_actions")
        then {platform, entity_id, id, unique_id, device_id, disabled_by}
        elif (.entity_id | test("_2$")) then {platform, entity_id}
        else empty end]
      | sort_by(.entity_id, .unique_id)'
}

# ---- 0. ACL rows ------------------------------------------------------------------------------------------------------------
[ -f "$ACL" ] || abort "no ACL file"
[ -f "$ACL_BAK" ] || cp -p "$ACL" "$ACL_BAK" || abort "cannot back up the ACL"
if ! grep -qxF "$ACL_ROW" "$ACL"; then
  # insert the row inside the ha_one and ha_two blocks (a line belongs to the nearest preceding `user`)
  tmp=$(mktemp)
  awk -v row="$ACL_ROW" '
    /^user / { cur = $2 }
    { print }
    (cur == "ha_one" || cur == "ha_two") && $0 == "topic readwrite homeassistant/#" { print row }' "$ACL" >"$tmp"
  cat "$tmp" >"$ACL" # same inode and mode
  rm -f "$tmp"
fi
diff -u "$ACL_BAK" "$ACL" >"$EV/acl-diff.txt"
[ "$(grep -c -x -F "+$ACL_ROW" "$EV/acl-diff.txt")" -eq 2 ] || [ "$(grep -c -x -F "$ACL_ROW" "$ACL")" -eq 2 ] || abort "the ACL does not hold the export row in both instance blocks"
podman kill --signal HUP mosq >/dev/null 2>&1 || abort "SIGHUP to mosq failed"
sleep 3
podman exec mosq grep -c -x -F "$ACL_ROW" /mosquitto/config/acl >"$EV/acl-in-container.txt" 2>&1 || true
[ -z "$(read_topics "${EXPORT_PREFIX}/#")" ] || abort "something is already retained under ${EXPORT_PREFIX}/ before the export is on"
[ -z "$(read_topics 'homeassistant/device/#')" ] || abort "something is already retained under homeassistant/device/ before the export is on"
: >"$EV/options-flow.txt"
: >"$EV/export-shape-check.txt"
EID_A=$(entry_id a)
EID_B=$(entry_id b)
echo "hub entries (ids only): ha-a $EID_A, ha-b $EID_B" >>"$EV/options-flow.txt"
SA_A=$(podman inspect ha-a --format '{{.State.StartedAt}}' | sed -e 's/ m=.*//')
SA_B=$(podman inspect ha-b --format '{{.State.StartedAt}}' | sed -e 's/ m=.*//')

# ---- clause 1: export on, default prefix --------------------------------------------------------------------------------
set_options a true "$EXPORT_PREFIX"
sleep "$WAIT_APPLY"
shape_check "default prefix" "$EXPORT_PREFIX" export-topics-default-prefix.txt
if [ -z "$(sed -n '/^$/!p' "$EV/export-topics-default-prefix.txt")" ]; then
  abort "no export topic read back under ${EXPORT_PREFIX}/ after 20 s: the ACL is not live or the options flow did not apply"
fi
if [ -z "$(read_topics 'homeassistant/device/+/config')" ]; then
  res PASS "X5" "nothing retained on homeassistant/device/+/config"
else
  res FAIL "X5" "retained on homeassistant/device: $(read_topics 'homeassistant/device/+/config' | awk '{print $1}' | tr '\n' ' ')"
fi

# ---- clause 2: export on the core prefix, no restart ------------------------------------------------------------------------
set_options a true "$CORE_PREFIX"
sleep "$WAIT_APPLY"
if [ -z "$(read_topics "${EXPORT_PREFIX}/#")" ]; then
  res PASS "X6 old prefix" "no retained message under ${EXPORT_PREFIX}/ after the prefix change"
else
  res FAIL "X6 old prefix" "retained under the old prefix: $(read_topics "${EXPORT_PREFIX}/#" | awk '{print $1}' | tr '\n' ' ')"
fi
shape_check "core prefix" "$CORE_PREFIX" core-prefix-topics.txt
for l in a b; do
  live_rows "$l" >"$EV/registry-core-prefix-$l.json"
  f="$EV/registry-core-prefix-$l.json"
  for id in "${DEVS[@]}"; do
    n=$(jq --arg id "$id" '[.[] | select(.platform == "mqtt" and .unique_id == $id)] | length' "$f")
    d=$(jq -r --arg id "$id" '[.[] | select(.platform == "mqtt" and .unique_id == $id) | .disabled_by] | join(",")' "$f")
    [ "$n" = 1 ] && [ "$d" = integration ] && res PASS "X7 ha-$l $id" "one mqtt row, disabled_by integration" ||
      res FAIL "X7 ha-$l $id" "mqtt rows with this unique id: $n, disabled_by: '$d'"
    n=$(jq --arg id "$id" '[.[] | select(.platform == "mqtt_actions" and .unique_id == $id and .disabled_by == null)] | length' "$f")
    [ "$n" = 1 ] && res PASS "X9 ha-$l $id" "native row present and enabled" || res FAIL "X9 ha-$l $id" "enabled native rows with this unique id: $n"
  done
  n=$(jq '[.[] | select(.platform == "mqtt" and .disabled_by == null)] | length' "$f")
  [ "$n" = 0 ] && res PASS "X8 ha-$l" "no enabled mqtt row" || res FAIL "X8 ha-$l" "$n enabled mqtt row(s): $(jq -c '[.[] | select(.platform == "mqtt" and .disabled_by == null) | .entity_id]' "$f")"
done

# ---- clause 3: export off -------------------------------------------------------------------------------------------------
set_options a false "$CORE_PREFIX"
sleep "$WAIT_APPLY"
{
  echo "== ${EXPORT_PREFIX}/# (retained, 3 s)"
  read_topics "${EXPORT_PREFIX}/#"
  echo "== homeassistant/device/# (retained, 3 s)"
  read_topics 'homeassistant/device/#'
  echo "== end"
} >"$EV/topics-after-off.txt"
left=$(sed -n '/^== /!p' "$EV/topics-after-off.txt" | sed '/^$/d')
[ -z "$left" ] && res PASS "X10" "no retained message under ${EXPORT_PREFIX}/ or homeassistant/device/ after the export was switched off" ||
  res FAIL "X10" "retained after off: $(awk '{print $1}' <<<"$left" | tr '\n' ' ')"
for l in a b; do
  live_rows "$l" >"$EV/registry-after-off-$l.json"
  res INFO "after off ha-$l (observation)" "mqtt rows left: $(jq '[.[] | select(.platform == "mqtt")] | length' "$EV/registry-after-off-$l.json")"
done

# the stored prefix goes back to the default (export stays off); nothing may appear on any topic because of it
set_options a false "$EXPORT_PREFIX"
sleep 5
[ -z "$(read_topics "${EXPORT_PREFIX}/#")" ] && [ -z "$(read_topics 'homeassistant/device/#')" ] ||
  res FAIL "X10 reset" "a retained message appeared after the prefix was reset to the default"

# ---- same process lifetime -----------------------------------------------------------------------------------------------------
[ "$(podman inspect ha-a --format '{{.State.StartedAt}}' | sed -e 's/ m=.*//')" = "$SA_A" ] &&
  [ "$(podman inspect ha-b --format '{{.State.StartedAt}}' | sed -e 's/ m=.*//')" = "$SA_B" ] ||
  res FAIL "process lifetime" "an instance restarted during the run, the pre-restart observation is void"

{
  for l in "${RES[@]}"; do echo "$l"; done
  echo "containers: ha-a StartedAt=$SA_A ha-b StartedAt=$SA_B (unchanged during the run unless a FAIL line says so)"
} >"$EV/result.txt"
cat "$EV/result.txt"

fails=$(grep -c '^FAIL ' "$EV/result.txt")
if [ "$fails" -eq 0 ]; then
  verdict "$EV" PASS "clause 1 (shape on the default prefix), clause 2 (core prefix: one disabled mqtt row per exported device on ha-a and ha-b, no restart) and clause 3 (cleared on off) hold; see result.txt"
  echo "PASS UAT-04 $EV"
  exit 0
fi
verdict "$EV" FAIL "$(grep '^FAIL ' "$EV/result.txt" | tr '\n' ';')"
echo "FAIL UAT-04 ($fails failed expectation(s))"
exit 1
