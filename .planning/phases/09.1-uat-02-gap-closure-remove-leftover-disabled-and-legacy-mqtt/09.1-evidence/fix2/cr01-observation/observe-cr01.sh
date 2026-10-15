#!/usr/bin/env bash
# CR-01 bench observation (plan 09.1-11, Task 1). Observation only, never a UAT result.
# A renamed, enabled legacy test button next to an integration-disabled switch twin, with the legacy discovery still
# retained, across one graceful start of ha-a and ha-b (the scenario of
# test_the_catch_keeps_an_enabled_customized_button_next_to_a_disabled_twin_on_legacy_content).
#
#   observe-cr01.sh gate | pre | payload | publish | rename | restart | record | context | outcome
#
# Run from the repository root under ~/ha-test/phase9.1-fix2.env. Holds no secret: broker passwords and tokens are read by
# lib.sh and ha-test-guard from their 0600 files. Registry changes go through the WebSocket API only (ha-test-guard).
set -uo pipefail
HT="$HOME/ha-test"
# shellcheck source=/dev/null
. "$HT/bin/lib.sh"
GUARD="$HT/bin/ha-test-guard"

ID=11111111-aaaa-4aaa-8aaa-000000000001 # "Lampe Test", owner ha-a, mirrored natively on ha-b
TOPIC="homeassistant/device/$ID/config"
NAME="CR-01 kept button"
BASE_TOPIC=mqtt_actions
SW_VERSION=0.1.0
SETTLE_SECONDS=90
LETTERS=(a b)

E2="$(evidence_root)"
O="$E2/cr01-observation"
FIX=$(sed -n 's/^sha: //p' "$E2/00-preflight/build.txt" | head -n1)
# working files (payload, config document) live outside the repository
S="${CR01_STATE:-/tmp/akentner/claude-1000/-home-akentner-Projects-homeassistant-mqtt-actions-integration/20cfcefc-ebcc-4e22-ac9c-1af41fcdc723/scratchpad/cr01-state}"
mkdir -p "$O" "$S"

die() {
  echo "ABORT $*" >&2
  exit 2
}
running() { [ "$(podman inspect "$1" --format '{{.State.Running}}' 2>/dev/null)" = true ]; }
stop_both() {
  podman stop -t 60 ha-a ha-b >/dev/null 2>&1
  ! running ha-a && ! running ha-b || die "ha-a and ha-b did not stop"
}
start_both() {
  podman start ha-a ha-b >/dev/null 2>&1 || die "podman start failed"
  wait_http 8123 && wait_http 8124 || die "an instance did not come up"
}
now() { date -u +%FT%TZ; }

# rows of the running instance with platform mqtt whose unique id is ID or ID_test_* (fixed fields only)
live_rows() {
  "$GUARD" "$1" ws raw config/entity_registry/list 2>/dev/null |
    jq -S --arg id "$ID" '(if type == "object" and has("result") then .result else . end)
      | [.[] | select(.platform == "mqtt" and (.unique_id == $id or (.unique_id | startswith($id + "_test_"))))
         | {entity_id, unique_id, disabled_by, name}] | sort_by(.unique_id)'
}
# rows of the registry file with platform mqtt_actions whose unique id is ID or ID_test_* (the A7 comparison)
native_ids() {
  reg_rows "$HT/$1/.storage/core.entity_registry" |
    jq -r --arg id "$ID" '[.[] | select(.platform == "mqtt_actions") | .unique_id
      | select(. == $id or startswith($id + "_test_"))] | sort | .[]'
}

case "${1:-}" in
  gate)
    "$HT/bin/check-preflight.sh" --quick || die "check-preflight.sh --quick did not PASS"
    out=$(probe_sub -t 'homeassistant/device/#' -F '%t %r' -W 3 2>/dev/null)
    [ -z "$out" ] || die "something is retained on homeassistant/device/# before the observation"
    echo "gate PASS: preflight quick PASS, nothing retained on homeassistant/device/#"
    ;;

  pre) # pre-observation copy of both registries (outside the repository, 0700), then both start again
    base=$(cat "$HT/.current-backup-phase9.1-fix2") || die "no fix2 backup pointer"
    [ -d "$base" ] || die "fix2 backup base $base does not exist"
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    dst="$base/cr01-pre-$stamp"
    stop_both
    (
      umask 077
      mkdir -p "$dst/a" "$dst/b"
      chmod 700 "$dst" "$dst/a" "$dst/b"
      for l in a b; do
        cp -p "$HT/$l/.storage/core.entity_registry" "$HT/$l/.storage/core.device_registry" "$dst/$l/"
      done
    ) || die "pre-observation copy failed"
    echo "$dst" >"$S/pre-copy-path"
    start_both
    sleep "$SETTLE_SECONDS"
    "$HT/bin/check-preflight.sh" --quick || die "check-preflight.sh --quick did not PASS after the pre-observation start"
    echo "pre-observation copy at $dst ($(now)); both started, preflight quick PASS"
    ;;

  payload) # the legacy payload of ID, built exactly as build_payloads in check-uat02.sh does
    py="$(mount_root)/.venv/bin/python"
    [ -x "$py" ] || die "no .venv python at $py"
    top=$(git rev-parse --show-toplevel)
    owner=$(inst_id a)
    probe_sub -t "$BASE_TOPIC/v1/devices/$ID/config" -C 1 -W 5 -F '%p' >"$S/$ID.doc" 2>/dev/null
    [ -s "$S/$ID.doc" ] || die "no retained config document for $ID on the broker"
    (cd "$top" && "$py" - "$S" "$owner" "$BASE_TOPIC" "$SW_VERSION" "$ID") <<'PY' || die "payload builder failed"
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
      echo "CR-01 observation payload check (A7): built with custom_components.mqtt_actions.discovery.build_discovery"
      echo "from the retained config document of $ID, instance_id=$owner, sw_version=$SW_VERSION, base_topic=$BASE_TOPIC"
      echo "date: $(now)"
      echo "build: $FIX"
      echo
    } >"$pc"
    ident=$(jq -r '.device.identifiers[0]' "$S/$ID.json")
    if [ "$ident" = "mqtt_actions_$ID" ]; then
      echo "device identifier: $ident (expected mqtt_actions_$ID): yes" >>"$pc"
    else
      echo "device identifier: $ident (expected mqtt_actions_$ID): NO" >>"$pc"
      bad=1
    fi
    built=$(jq -r '[.components[] | select(has("unique_id")) | .unique_id] | sort | .[]' "$S/$ID.json")
    {
      echo "topic: $TOPIC, device name: $(jq -r '.device.name' "$S/$ID.json")"
      echo "built unique ids:"
      sed 's/^/  /' <<<"$built"
    } >>"$pc"
    for l in "${LETTERS[@]}"; do
      reg=$(native_ids "$l")
      {
        echo "registry of ha-$l (platform mqtt_actions, unique id = id or id_test_*):"
        sed 's/^/  /' <<<"$reg"
      } >>"$pc"
      if [ "$built" = "$reg" ]; then
        echo "ha-$l: built unique ids equal the registry rows: yes" >>"$pc"
      else
        echo "ha-$l: built unique ids equal the registry rows: NO" >>"$pc"
        bad=1
      fi
    done
    if [ "$bad" -eq 0 ]; then
      echo "result: built payload matches the registry unique ids on ha-a and ha-b" >>"$pc"
      echo "payload PASS"
    else
      echo "result: MISMATCH" >>"$pc"
      echo "payload MISMATCH, see $pc"
      exit 1
    fi
    ;;

  publish) # live replay: publish retained while both run (WR03-LIVE-REPLAY, D-07), then project the rows after 20 s
    running ha-a && running ha-b || die "publish: both instances must run"
    probe_pub -r -q 1 -t "$TOPIC" -f "$S/$ID.json" || die "publish to $TOPIC failed"
    back=$(probe_sub -t "$TOPIC" -C 1 -W 5 -F '%r %q %p' 2>/dev/null)
    [ -n "$back" ] || die "read-back of $TOPIC is empty"
    rflag=$(awk '{print $1}' <<<"$back")
    same=no
    [ "$(sed 's/^[^ ]* [^ ]* //' <<<"$back" | jq -S -c .)" = "$(jq -S -c . "$S/$ID.json")" ] && same=yes
    {
      echo
      echo "live publish: $(now), retained QoS 1 on $TOPIC while ha-a and ha-b run"
      echo "read-back: retained flag $rflag, payload equals the built payload: $same"
    } >>"$O/payload-check.txt"
    [ "$rflag" = 1 ] && [ "$same" = yes ] || die "read-back is not retained or differs from the published payload"
    sleep 20
    for l in "${LETTERS[@]}"; do
      live_rows "$l" >"$O/rows-after-publish-$l.json" || die "row query on ha-$l failed"
    done
    echo "publish done ($(now)); rows written"
    ;;

  rename) # rename the enabled replayed button with the lowest unique id on each instance with the expected shape
    : >"$S/renamed"
    {
      echo "CR-01 observation rename through config/entity_registry/update (WebSocket API, as the UI does)"
      echo "date: $(now)"
      echo "name: $NAME"
      echo
    } >"$O/rename.txt"
    for l in "${LETTERS[@]}"; do
      f="$O/rows-after-publish-$l.json"
      sw_ok=$(jq --arg id "$ID" '[.[] | select(.unique_id == $id and .disabled_by == "integration")] | length' "$f")
      btn=$(jq -r '[.[] | select((.entity_id | startswith("button.")) and .disabled_by == null)] | sort_by(.unique_id) | .[0].entity_id // empty' "$f")
      if [ "$sw_ok" -ne 1 ] || [ -z "$btn" ]; then
        echo "ha-$l: expected shape missing (integration-disabled switch rows: $sw_ok, enabled button: ${btn:-none}); not renamed, instance not-exercised" >>"$O/rename.txt"
        continue
      fi
      uid=$(jq -r --arg e "$btn" '.[] | select(.entity_id == $e) | .unique_id' "$f")
      resp=$("$GUARD" "$l" ws raw config/entity_registry/update "$(jq -cn --arg e "$btn" --arg n "$NAME" '{entity_id: $e, name: $n}')" 2>/dev/null)
      got=$(jq -c '(if type == "object" and has("result") then .result else . end) | .entity_entry // . | {name, disabled_by}' <<<"$resp" 2>/dev/null)
      echo "ha-$l: entity_id $btn, unique_id $uid, returned ${got:-<no answer>}" >>"$O/rename.txt"
      echo "$l $btn $uid" >>"$S/renamed"
    done
    cat "$O/rename.txt"
    ;;

  restart) # one graceful start with the legacy message still retained (LEGACY content)
    sleep 10
    stop_both
    start_both
    echo "started $(now) (ha-a $(podman inspect ha-a --format '{{.State.StartedAt}}' | sed 's/ m=.*//'))" >"$S/restart-at"
    sleep "$SETTLE_SECONDS"
    cat "$S/restart-at"
    ;;

  record)
    for l in "${LETTERS[@]}"; do
      live_rows "$l" >"$O/rows-after-restart-$l.json" || die "row query on ha-$l failed"
    done
    meta=$(probe_sub -t "$TOPIC" -C 1 -W 5 -F '%r %l' 2>/dev/null)
    pl=$(probe_sub -t "$TOPIC" -C 1 -W 5 -F '%p' 2>/dev/null)
    same=no
    [ -n "$pl" ] && [ "$(jq -S -c . <<<"$pl" 2>/dev/null)" = "$(jq -S -c . "$S/$ID.json")" ] && same=yes
    {
      echo "retained read of $TOPIC after the start with LEGACY content ($(now))"
      if [ -n "$meta" ]; then
        echo "retained payload present: yes (retained flag $(awk '{print $1}' <<<"$meta"))"
        echo "length: $(awk '{print $2}' <<<"$meta") bytes"
      else
        echo "retained payload present: no"
        echo "length: 0"
      fi
      echo "JSON equals the published payload: $same"
    } >"$O/retained.txt"
    pat='Removed [0-9]* duplicate entities|Disabled [0-9]* duplicate entities|keeps its MQTT device|postponed|Kept the MQTT entities of [0-9]* native devices|could not clear the discovery'
    for l in "${LETTERS[@]}"; do
      {
        echo "ha-$l, $(cat "$S/restart-at"); lines of this start matching the observation patterns (timestamp and text)"
        sed 's/\x1b\[[0-9;]*m//g' "$HT/$l/home-assistant.log" 2>/dev/null | grep -E "$pat" |
          sed -E 's/^([0-9-]+ [0-9:.]+) [A-Z]+ \([^)]*\) \[[^]]*\] /\1 /' | cut -c1-400 || true
      } >"$O/log-$l.txt"
    done
    echo "record done"
    ;;

  context) # added after the first outcome read contradicts: where the rows went (fixed fields only), and the log context
    for l in "${LETTERS[@]}"; do
      "$GUARD" "$l" ws raw config/entity_registry/list 2>/dev/null |
        jq -S --arg id "$ID" '(if type == "object" and has("result") then .result else . end)
          | [.[] | select(.platform == "mqtt_actions" and (.unique_id == $id or (.unique_id | startswith($id + "_"))))
             | {entity_id, unique_id, disabled_by, name}] | sort_by(.unique_id)' >"$O/rows-native-after-restart-$l.json" ||
        die "native row query on ha-$l failed"
      tmp=$(mktemp)
      cp "$HT/$l/.storage/core.entity_registry" "$tmp"
      jq -S --arg id "$ID" '[.data.deleted_entities[]
          | select((.platform == "mqtt" or .platform == "mqtt_actions") and (.unique_id | startswith($id)))
          | {platform, entity_id, unique_id, disabled_by, name, modified_at}] | sort_by(.platform, .unique_id)' "$tmp" \
        >"$O/deleted-after-restart-$l.json"
      rm -f "$tmp"
      {
        echo "ha-$l, $(cat "$S/restart-at"); lines of this start from custom_components.mqtt_actions and"
        echo "homeassistant.components.mqtt.discovery (timestamp, logger and text)"
        sed 's/\x1b\[[0-9;]*m//g' "$HT/$l/home-assistant.log" 2>/dev/null |
          grep -E '\[(custom_components\.mqtt_actions|homeassistant\.components\.mqtt\.discovery)' |
          sed -E 's/^([0-9-]+ [0-9:.]+) [A-Z]+ \([^)]*\) /\1 /' | cut -c1-400 || true
      } >"$O/log-context-$l.txt"
    done
    echo "context done"
    ;;

  outcome)
    topic_ok=no
    grep -qx 'retained payload present: yes.*' "$O/retained.txt" && ! grep -qx 'length: 0 bytes' "$O/retained.txt" && topic_ok=yes
    overall=not-exercised
    any_exp=0
    any_con=0
    lines=()
    for l in "${LETTERS[@]}"; do
      read -r _ btn uid < <(grep "^$l " "$S/renamed" 2>/dev/null) || true
      after="$O/rows-after-restart-$l.json"
      pp=$(grep -c 'postponed' "$O/log-$l.txt")
      rm_=$(grep -c 'Removed [0-9]* duplicate entities' "$O/log-$l.txt")
      sw=$(jq --arg id "$ID" '[.[] | select(.unique_id == $id and .disabled_by == "integration")] | length' "$after")
      sw_yes=no
      [ "$sw" -ge 1 ] && sw_yes=yes
      if [ -z "${uid:-}" ]; then
        cls=not-exercised
        lines+=("ha-$l: $cls (no button was renamed: the expected shape was missing after the publish); switch twin present with disabled_by integration $sw_yes, TOPIC retained non-empty $topic_ok, postponed lines $pp, Removed lines $rm_")
        unset btn uid
        continue
      fi
      present=$(jq --arg u "$uid" '[.[] | select(.unique_id == $u)] | length' "$after")
      named_en=$(jq --arg u "$uid" --arg n "$NAME" '[.[] | select(.unique_id == $u and .name == $n and .disabled_by == null)] | length' "$after")
      b_yes=no
      [ "$named_en" -ge 1 ] && b_yes=yes
      # the renamed row may also survive moved to platform mqtt_actions by the takeover (WR-04): then it is not gone
      nat="$O/rows-native-after-restart-$l.json"
      moved=0
      [ -s "$nat" ] && moved=$(jq --arg u "$uid" --arg n "$NAME" '[.[] | select(.unique_id == $u and .name == $n and .disabled_by == null)] | length' "$nat")
      m_yes=no
      [ "$moved" -ge 1 ] && m_yes=yes
      if { [ "$present" -eq 0 ] && [ "$m_yes" = no ]; } || [ "$topic_ok" = no ]; then
        cls=contradicts
        any_con=1
      elif [ "$pp" -eq 0 ] && [ "$b_yes" = yes ] && [ "$sw_yes" = yes ] && [ "$topic_ok" = yes ]; then
        cls=exercised-as-expected
        any_exp=1
      else
        cls=not-exercised
      fi
      lines+=("ha-$l: $cls; renamed button $btn ($uid) present on platform mqtt with NAME and enabled $b_yes, moved to platform mqtt_actions with NAME and enabled $m_yes, switch twin present with disabled_by integration $sw_yes, TOPIC retained non-empty $topic_ok, postponed lines $pp, Removed lines $rm_")
      unset btn uid
    done
    if [ "$any_con" -eq 1 ]; then
      overall=contradicts
    elif [ "$any_exp" -eq 1 ]; then
      overall=exercised-as-expected
    fi
    {
      echo "$overall"
      printf '%s\n' "${lines[@]}"
      echo "observation only, never a UAT result; classes fixed in 09.1-11-PLAN.md before the run"
      echo "build: $FIX"
    } >"$O/outcome.txt"
    cat "$O/outcome.txt"
    ;;

  *)
    echo "usage: observe-cr01.sh gate | pre | payload | publish | rename | restart | record | context | outcome" >&2
    exit 2
    ;;
esac
