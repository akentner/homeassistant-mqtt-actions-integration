#!/usr/bin/env bash
# Phase 8, plan 08-03 task 1: import the countable "UAT Marker" switch on ha-a (owner) and wait for the unapproved mirror
# on ha-b. Writes ~/ha-test/.fixtures.env and uat-03/{export-shape.json,fixture.txt}. Run from inside the evidence checkout.
#   setup-marker.sh MARKER_JSON_FILE
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"
G="$here/ha-test-guard"
EV="$(evidence_root)/uat-03${PHASE8_EV_SUFFIX:-}"
mkdir -p "$EV"

[ -f "$HT/.fixtures.env" ] && grep -q '^MARKER_ID=' "$HT/.fixtures.env" && {
  echo "ABORT marker already recorded in .fixtures.env" >&2
  exit 2
}

body=$(tr -d '\n' <"$1")
resp=$("$G" a rest POST '/api/services/mqtt_actions/import_devices?return_response' "$body")
echo "import response: $resp" >&2
uuid=$(jq -r '.service_response.imported[0].uuid // empty' <<<"$resp")
[ -n "$uuid" ] || {
  echo "ABORT no uuid in the import response" >&2
  exit 2
}
echo "MARKER_ID=$uuid" >"$HT/.fixtures.env"

ent_a=""
ent_b=""
for _ in $(seq 1 30); do
  ent_a=$("$G" a ws raw get_states | jq -r '[.result[] | select(.attributes.friendly_name=="UAT Marker") | .entity_id][0] // empty')
  ent_b=$("$G" b ws raw get_states | jq -r '[.result[] | select(.attributes.friendly_name=="UAT Marker") | .entity_id][0] // empty')
  [ -n "$ent_a" ] && [ -n "$ent_b" ] && break
  sleep 2
done

{
  echo "marker name: UAT Marker"
  echo "marker uuid: $uuid"
  echo "owner: ha-a ($(inst_id a))"
  echo "entity ha-a: ${ent_a:-MISSING}"
  echo "entity ha-b: ${ent_b:-MISSING}"
  echo "actions: system_log.write level warning, message 'UAT03-MARKER on' (to on) and 'UAT03-MARKER off' (to off)"
  echo "created: $(date -u +%Y-%m-%dT%H:%M:%SZ) via mqtt_actions.import_devices (data)"
} >"$EV/fixture.txt"
cat "$EV/fixture.txt"
[ -n "$ent_a" ] && [ -n "$ent_b" ] || exit 1
