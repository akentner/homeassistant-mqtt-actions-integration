#!/usr/bin/env bash
# UAT-01: a v0.1.0 instance (ha-c) next to two native instances keeps running its actions for the migrated devices, shows no
# entities for them and raises no error. Phase 8, plan 08-05.
#   check-uat01.sh run     marker changes, registry, errors, broker topics, then stops ha-c and checks its availability
# Run from inside the checkout that holds the evidence. Exit: 0 PASS, 1 FAIL, 2 ABORT (bench problem, never a UAT result).
#
# EXPECTED VALUES AND THE WORDING POLICY ARE CODED HERE, BEFORE ANYTHING IS OBSERVED (D-08, Pitfall 6).
# Owner decision UAT01-WORDING (2026-10-06): UAT01_MODE_SELECT=observation. The v0.1.0 companion mode selects (platform
# mqtt_actions, unique id "{device id}_mode") are recorded and do NOT fail the check. The check fails on
#   - any row of platform `mqtt` on ha-c,
#   - any row (any platform) whose unique id equals a migrated device id or starts with "{device id}_test_",
#   - any mqtt_actions row for a migrated device that is not "{device id}_mode" (switch, button or other select),
#   - an action run count on ha-c, ha-a or ha-b that is not exactly +1 per marker state change,
#   - an ERROR or CRITICAL line naming custom_components.mqtt_actions or homeassistant.components.mqtt in ha-c's log, or in
#     the logs of ha-a and ha-b after ha-c arrived,
#   - a Repairs issue on ha-c that is neither an approval request of an unapproved mirror nor one of the two known core bench
#     artifacts (homeassistant/country_not_configured, http/yaml_still_present_after_migration, both unrelated to the
#     integration and present on a fresh instance with a YAML http block),
#   - any retained topic under homeassistant/ on the broker (no new Discovery topic).
# Counting rule (as in UAT-03): per instance the number of log lines with the exact marker text before and after each step,
# inside one process lifetime; a step waits 60 s after the trigger, so delta == 1 also rules out a late echo or replay run.
# The marker switch is on a known state at the start; the first change goes to the opposite state and the second one back
# (the plan text assumed state on; the bench state is off, so the order is turn_on then turn_off).
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"
G="$here/ha-test-guard"

[ "${1:-}" = run ] || {
  echo "usage: check-uat01.sh run" >&2
  exit 2
}

UAT01_MODE_SELECT=observation
EV="$(evidence_root)/uat-01"
mkdir -p "$EV"
MARKER_ID=$(sed -n 's/^MARKER_ID=//p' "$HT/.fixtures.env" 2>/dev/null | head -n1)
ENT=switch.uat_marker
WAIT_CMD=60
P_ON="UAT03-MARKER on"
P_OFF="UAT03-MARKER off"
ALLOWED_CORE_ISSUES='homeassistant/country_not_configured http/yaml_still_present_after_migration'

abort() {
  echo "ABORT $1" >&2
  verdict "$EV" ABORT "$1"
  exit 2
}

[ -n "$MARKER_ID" ] || abort "no MARKER_ID in .fixtures.env"
"$here/check-hac.sh" ready >/dev/null || abort "check-hac.sh ready does not print PASS"
"$here/check-preflight.sh" --quick >/dev/null || abort "check-preflight.sh --quick does not print PASS"
IID_C=$(inst_id c)
[ -n "$IID_C" ] || abort "no instance id of ha-c"

RES=()
res() { RES+=("$1 $2 :: $3"); }
cnt() { # cnt LETTER PATTERN
  local n
  n=$(grep -c -F -- "$2" "$HT/$1/home-assistant.log" 2>/dev/null)
  echo "${n:-0}"
}
snap() { # -> "a_on a_off b_on b_off c_on c_off"
  echo "$(cnt a "$P_ON") $(cnt a "$P_OFF") $(cnt b "$P_ON") $(cnt b "$P_OFF") $(cnt c "$P_ON") $(cnt c "$P_OFF")"
}
delta() { awk -v i="$3" -v b="$1" -v a="$2" 'BEGIN{split(b,x," ");split(a,y," ");print y[i]-x[i]}'; }
expect() { # expect LABEL OBSERVED EXPECTED
  if [ "$2" -eq "$3" ]; then res PASS "$1" "delta $2 (expected $3)"; else res FAIL "$1" "observed delta $2, expected $3"; fi
}
estate() { "$G" "$1" ws raw get_states | jq -r --arg e "$ENT" '[.result[] | select(.entity_id==$e) | .state][0] // "missing"'; }

COUNTS="$EV/counts.txt"
{
  echo "UAT-01 marker counts (log lines with the exact text, one process lifetime per instance)"
  echo "columns: a_on a_off b_on b_off c_on c_off   (a = ha-a native owner, b = ha-b native, c = ha-c v0.1.0 straggler)"
} >"$COUNTS"

# ---- 1 keeps running its actions ------------------------------------------------------------------------------------------
S0=$(estate a)
case "$S0" in on) FIRST=turn_off ;; off) FIRST=turn_on ;; *) abort "marker state on ha-a is '$S0'" ;; esac
[ "$FIRST" = turn_on ] && { T1="$P_ON"; I1_A=1; I1_B=3; I1_C=5; T2="$P_OFF"; SECOND=turn_off; I2_A=2; I2_B=4; I2_C=6; } ||
  { T1="$P_OFF"; I1_A=2; I1_B=4; I1_C=6; T2="$P_ON"; SECOND=turn_on; I2_A=1; I2_B=3; I2_C=5; }
echo "start state of the marker on ha-a: $S0; change 1: switch.$FIRST (\"$T1\"); change 2: switch.$SECOND (\"$T2\")" >>"$COUNTS"

B0=$(snap)
"$G" a ws call "switch.$FIRST" "{\"entity_id\":\"$ENT\"}" >/dev/null || abort "switch.$FIRST on ha-a failed"
sleep "$WAIT_CMD"
B1=$(snap)
{ echo "change 1 before: $B0"; echo "change 1 after:  $B1"; } >>"$COUNTS"
expect "1.1 ha-a runs \"$T1\" once" "$(delta "$B0" "$B1" $I1_A)" 1
expect "1.1 ha-b runs \"$T1\" once" "$(delta "$B0" "$B1" $I1_B)" 1
expect "1.1 ha-c (v0.1.0) runs \"$T1\" once" "$(delta "$B0" "$B1" $I1_C)" 1
expect "1.1 no \"$T2\" line on ha-c" "$(delta "$B0" "$B1" $I2_C)" 0

"$G" a ws call "switch.$SECOND" "{\"entity_id\":\"$ENT\"}" >/dev/null || abort "switch.$SECOND on ha-a failed"
sleep "$WAIT_CMD"
B2=$(snap)
{ echo "change 2 before: $B1"; echo "change 2 after:  $B2"; } >>"$COUNTS"
expect "1.2 ha-a runs \"$T2\" once" "$(delta "$B1" "$B2" $I2_A)" 1
expect "1.2 ha-b runs \"$T2\" once" "$(delta "$B1" "$B2" $I2_B)" 1
expect "1.2 ha-c (v0.1.0) runs \"$T2\" once" "$(delta "$B1" "$B2" $I2_C)" 1
expect "1.2 no \"$T1\" line on ha-c" "$(delta "$B1" "$B2" $I1_C)" 0
S_END=$(estate a)
[ "$S_END" = "$S0" ] && res PASS "1.3 marker back at its start state" "$S_END" || res FAIL "1.3 marker back at its start state" "now $S_END, start $S0"

# ---- 2 no entities for migrated devices -----------------------------------------------------------------------------------
DEVICES=$(probe_sub -t 'mqtt_actions/v1/devices/+/config' -v -W 3 -F '%t' 2>/dev/null | sed -n 's#^mqtt_actions/v1/devices/\([^/]*\)/config$#\1#p' | sort)
NDEV=$(wc -l <<<"$DEVICES" | tr -d ' ')
[ -n "$DEVICES" ] || abort "no retained config topics read back"
res PASS "2.0 migrated devices read from the retained config topics" "$NDEV devices"

REG=$("$G" c ws raw config/entity_registry/list) || abort "entity registry of ha-c not readable"
ST=$("$G" c ws raw get_states) || abort "states of ha-c not readable"
DEV_JSON=$(jq -Rn '[inputs | select(length>0)]' <<<"$DEVICES")
jq -n --argjson reg "$REG" --argjson st "$ST" '{
    registry_rows: [$reg.result[] | select(.platform=="mqtt" or .platform=="mqtt_actions")
                    | {platform, entity_id, unique_id, device_id, disabled_by, entity_category}] | sort_by(.entity_id),
    registry_row_count_all_platforms: ($reg.result | length),
    states: [$st.result[] | select(.entity_id | test("^(switch|select|button|sensor)\\.")) | {entity_id, state}] | sort_by(.entity_id)
  }' >"$EV/registry-c.json"

N_MQTT=$(jq '[.registry_rows[] | select(.platform=="mqtt")] | length' "$EV/registry-c.json")
[ "$N_MQTT" -eq 0 ] && res PASS "2.1 no row of platform mqtt on ha-c" "0 rows" || res FAIL "2.1 no row of platform mqtt on ha-c" "$N_MQTT rows"

BAD_ID=$(jq -r --argjson d "$DEV_JSON" --argjson reg "$REG" '
  [$reg.result[] | .unique_id as $u | select($u != null) | select(any($d[]; . as $id | $u == $id or ($u | startswith($id + "_test_")))) | .entity_id] | join(",")' <<<"null")
[ -z "$BAD_ID" ] && res PASS "2.2 no row with unique id = device id or {id}_test_*" "none" || res FAIL "2.2 no row with unique id = device id or {id}_test_*" "$BAD_ID"

BAD_PLATFORM=$(jq -r --argjson d "$DEV_JSON" '
  [.registry_rows[] | select(.platform=="mqtt_actions") | .unique_id as $u
   | select(any($d[]; . as $id | $u | startswith($id)))
   | select(($u | endswith("_mode")) | not) | .entity_id] | join(",")' "$EV/registry-c.json")
[ -z "$BAD_PLATFORM" ] && res PASS "2.3 no switch, button or other select of mqtt_actions for a migrated device" "none" ||
  res FAIL "2.3 no switch, button or other select of mqtt_actions for a migrated device" "$BAD_PLATFORM"

MODE_ROWS=$(jq -r --argjson d "$DEV_JSON" '
  [.registry_rows[] | select(.platform=="mqtt_actions") | .unique_id as $u
   | select(any($d[]; . as $id | $u == ($id + "_mode"))) | .entity_id] | sort | join(" ")' "$EV/registry-c.json")
N_MODE=$(wc -w <<<"$MODE_ROWS" | tr -d ' ')
N_SW=$(jq '[.states[] | select(.entity_id | startswith("switch."))] | length' "$EV/registry-c.json")
[ "$N_SW" -eq 0 ] && res PASS "2.4 no switch state on ha-c" "0" || res FAIL "2.4 no switch state on ha-c" "$N_SW switch states"
case "$UAT01_MODE_SELECT" in
  observation) res OBSERVED "2.5 companion mode selects (policy: observation, recorded, not counted)" "$N_MODE of $NDEV: $MODE_ROWS" ;;
  strict) [ "$N_MODE" -eq 0 ] && res PASS "2.5 no mode select (policy: strict)" "0" || res FAIL "2.5 mode selects exist (policy: strict)" "$N_MODE: $MODE_ROWS" ;;
esac

# ---- 3 raises no error ----------------------------------------------------------------------------------------------------
LOGC="$HT/c/home-assistant.log"
ERR_RE='(ERROR|CRITICAL).*(custom_components\.mqtt_actions|homeassistant\.components\.mqtt)'
{
  echo "# ha-c log, filtered: lines naming custom_components.mqtt_actions, homeassistant.components.mqtt or the marker texts"
  grep -E 'custom_components\.mqtt_actions|homeassistant\.components\.mqtt|UAT03-MARKER' "$LOGC" | cut -c1-300
  echo
  echo "# ha-c log: other ERROR or CRITICAL lines (not part of the criterion; container capability limits of the bench image)"
  grep -E ' (ERROR|CRITICAL) ' "$LOGC" | grep -Ev 'custom_components\.mqtt_actions|homeassistant\.components\.mqtt' | cut -c1-200
} >"$EV/log-c.txt"
# the container output covers every process lifetime of ha-c since its creation (the file log only the current one)
CONT_OUT=$(mktemp)
podman logs ha-c >"$CONT_OUT" 2>&1
N_ERR_C=$(grep -cE "$ERR_RE" "$CONT_OUT")
N_ERR_C_FILE=$(grep -cE "$ERR_RE" "$LOGC")
{
  echo
  echo "# whole container output of ha-c since its creation (all process lifetimes): lines at ERROR or CRITICAL naming mqtt_actions or core mqtt: $N_ERR_C; current log file: $N_ERR_C_FILE"
} >>"$EV/log-c.txt"
rm -f "$CONT_OUT"
[ "$N_ERR_C" -eq 0 ] && [ "$N_ERR_C_FILE" -eq 0 ] && res PASS "3.1 no ERROR or CRITICAL of mqtt_actions or core mqtt in the log of ha-c" "0 lines (container output of all lifetimes and current log file)" ||
  res FAIL "3.1 error lines in the log of ha-c" "$N_ERR_C in the container output, $N_ERR_C_FILE in the current log"

ISS=$("$G" c ws raw repairs/list_issues) || abort "repairs not readable on ha-c"
jq -r '.result.issues[] | "\(.domain)/\(.issue_id)"' <<<"$ISS" | sort >"$EV/issues-c.txt"
BAD_ISS=""
while read -r i; do
  case "$i" in
    mqtt_actions/approval_"$MARKER_ID") BAD_ISS="$BAD_ISS $i(marker approval pending)" ;;
    mqtt_actions/approval_*) ;;
    *) case " $ALLOWED_CORE_ISSUES " in *" $i "*) ;; *) BAD_ISS="$BAD_ISS $i" ;; esac ;;
  esac
done <"$EV/issues-c.txt"
[ -z "$BAD_ISS" ] && res PASS "3.2 Repairs on ha-c hold only approval requests (plus two known core bench artifacts)" "$(wc -l <"$EV/issues-c.txt" | tr -d ' ') issues, see issues-c.txt" ||
  res FAIL "3.2 unexpected Repairs issue on ha-c" "$BAD_ISS"

# arrival of ha-c = creation time of its hub entry (one non-secret field)
ARR_UTC=$(jq -r '.data.entries[] | select(.domain=="mqtt_actions") | .created_at' "$HT/c/.storage/core.config_entries" 2>/dev/null | head -n1)
ARR=$(TZ=Europe/Berlin date -d "$ARR_UTC" '+%Y-%m-%d %H:%M:%S')
{
  echo "# ha-a and ha-b: lines at WARNING, ERROR or CRITICAL naming mqtt_actions or core mqtt since ha-c arrived ($ARR local, hub entry created $ARR_UTC)"
  for l in a b; do
    echo "## ha-$l"
    awk -v t="$ARR" 'substr($0,1,19) >= t' "$HT/$l/home-assistant.log" | grep -E ' (WARNING|ERROR|CRITICAL) .*(custom_components\.mqtt_actions|homeassistant\.components\.mqtt)' | cut -c1-300
  done
  echo "# (empty sections mean none)"
} >"$EV/log-a-b-after-arrival.txt"
N_ERR_AB=0
for l in a b; do
  n=$(awk -v t="$ARR" 'substr($0,1,19) >= t' "$HT/$l/home-assistant.log" | grep -cE "$ERR_RE")
  N_ERR_AB=$((N_ERR_AB + n))
done
[ "$N_ERR_AB" -eq 0 ] && res PASS "3.3 no new mqtt_actions or core mqtt ERROR on ha-a and ha-b since ha-c arrived" "0 lines (since $ARR)" ||
  res FAIL "3.3 new error lines on ha-a or ha-b" "$N_ERR_AB lines"

# broker: retained topics now, names and retain flag only (availability payloads too), compared with the preflight snapshot
SNAP="$(dirname "$EV")/00-preflight/retained-snapshot.txt"
{
  echo "# retained topics now (topic only; payload shown for availability topics)"
  probe_sub -t '#' -v -W 4 -F '%t %r %p' --retained-only 2>/dev/null | grep -v '^\$SYS' |
    awk '{ if ($1 ~ /availability$/) print $1, $2, $3; else print $1, $2, "(payload not listed)" }' | sort
} >"$EV/broker-topics.txt"
awk '!/^#/ {print $1}' "$EV/broker-topics.txt" | sort -u >"$EV/.now"
awk '{print $1}' "$SNAP" | sort -u >"$EV/.then"
NEW_TOPICS=$(comm -13 "$EV/.then" "$EV/.now" | tr '\n' ' ')
GONE_TOPICS=$(comm -23 "$EV/.then" "$EV/.now" | tr '\n' ' ')
rm -f "$EV/.now" "$EV/.then"
{
  echo "# new retained topics compared with 00-preflight/retained-snapshot.txt: ${NEW_TOPICS:-none}"
  echo "# topics of the snapshot no longer retained: ${GONE_TOPICS:-none}"
} >>"$EV/broker-topics.txt"
N_HA=$(grep -c '^homeassistant/' "$EV/broker-topics.txt" || true)
[ "$N_HA" -eq 0 ] && res PASS "3.4 no retained topic under homeassistant/ (no new Discovery topic)" "0 topics" ||
  res FAIL "3.4 retained topic(s) under homeassistant/" "$N_HA"
res INFO "3.5 new retained topics against the preflight snapshot" "${NEW_TOPICS:-none}"

# ---- stop ha-c and read its availability -----------------------------------------------------------------------------------
podman stop -t 60 ha-c >/dev/null 2>&1
sleep 3
AV=$(probe_sub -t "mqtt_actions/v1/instances/$IID_C/availability" -C 1 -W 4 2>/dev/null || true)
CLEARED=no
if [ "$AV" = online ]; then
  probe_pub -r -n -t "mqtt_actions/v1/instances/$IID_C/availability"
  CLEARED=yes
  sleep 1
  AV2=$(probe_sub -t "mqtt_actions/v1/instances/$IID_C/availability" -C 1 -W 4 2>/dev/null || true)
else
  AV2=$AV
fi
if [ "$(podman inspect ha-c --format '{{.State.Running}}')" = false ]; then
  res PASS "4.1 ha-c stopped" "container down"
else
  res FAIL "4.1 ha-c stopped" "still running"
fi
res INFO "4.2 retained availability of ha-c after the stop" "${AV:-empty} (topic cleared by hand: $CLEARED; after: ${AV2:-empty})"
[ "$AV2" != online ] && res PASS "4.3 availability is not online" "${AV2:-empty}" || res FAIL "4.3 availability is not online" "$AV2"

# ---- write result and verdict ----------------------------------------------------------------------------------------------
{
  echo "UAT-01 result; policy UAT01_MODE_SELECT=$UAT01_MODE_SELECT (owner decision UAT01-WORDING, 2026-10-06)"
  echo "ha-c instance id: $IID_C; start state of the marker: $S0; migrated devices: $NDEV"
  printf '%s\n' "${RES[@]}"
} >"$EV/result.txt"
FAILS=$(printf '%s\n' "${RES[@]}" | grep -c '^FAIL')
if [ "$FAILS" -eq 0 ]; then
  verdict "$EV" PASS "all assertions hold under the policy $UAT01_MODE_SELECT; $N_MODE companion mode selects recorded as observation; see result.txt"
  cat "$EV/result.txt"
  exit 0
fi
verdict "$EV" FAIL "$FAILS assertion(s) failed; see result.txt"
cat "$EV/result.txt"
exit 1
