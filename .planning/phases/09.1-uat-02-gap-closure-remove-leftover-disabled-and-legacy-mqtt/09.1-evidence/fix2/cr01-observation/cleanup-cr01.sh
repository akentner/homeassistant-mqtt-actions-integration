#!/usr/bin/env bash
# Cleanup after the CR-01 bench observation (plan 09.1-11, Task 2). Bench hygiene after all verdicts, never a result.
#   cleanup-cr01.sh reset | clear | restart | check | restore | final
# Each step appends its time and result to cr01-observation/cleanup.txt. Run from the repository root under
# ~/ha-test/phase9.1-fix2.env. Holds no secret. Registry changes go through the WebSocket API only, except the plan's
# fallback (restore), which copies the pre-observation registry files back while both instances are stopped.
set -uo pipefail
HT="$HOME/ha-test"
# shellcheck source=/dev/null
. "$HT/bin/lib.sh"
GUARD="$HT/bin/ha-test-guard"
ID=11111111-aaaa-4aaa-8aaa-000000000001
TOPIC="homeassistant/device/$ID/config"
NAME="CR-01 kept button"
LETTERS=(a b)
O="$(evidence_root)/cr01-observation"
C="$O/cleanup.txt"
S="${CR01_STATE:-/tmp/akentner/claude-1000/-home-akentner-Projects-homeassistant-mqtt-actions-integration/20cfcefc-ebcc-4e22-ac9c-1af41fcdc723/scratchpad/cr01-state}"

now() { date -u +%FT%TZ; }
log() { echo "$*" | tee -a "$C"; }
die() {
  log "ABORT $*"
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
retained_any() { probe_sub -t 'homeassistant/device/#' -F '%t %r' -W 3 2>/dev/null; }

case "${1:-}" in
  reset) # step 1: name back to null on every live row named NAME, any platform
    log "== step 1 reset the name ($(now))"
    for l in "${LETTERS[@]}"; do
      ids=$("$GUARD" "$l" ws raw config/entity_registry/list 2>/dev/null |
        jq -r --arg n "$NAME" '(if type == "object" and has("result") then .result else . end) | .[] | select(.name == $n) | .entity_id')
      if [ -z "$ids" ]; then
        log "ha-$l: no live row named \"$NAME\""
        continue
      fi
      for e in $ids; do
        got=$("$GUARD" "$l" ws raw config/entity_registry/update "$(jq -cn --arg e "$e" '{entity_id: $e, name: null}')" 2>/dev/null |
          jq -c '(if type == "object" and has("result") then .result else . end) | .entity_entry // . | {entity_id, platform, name, disabled_by}')
        log "ha-$l: reset name of $e, returned ${got:-<no answer>}"
      done
    done
    ;;

  clear) # step 2: empty retained publish on TOPIC, read back empty
    log "== step 2 clear the topic ($(now))"
    probe_pub -r -q 1 -t "$TOPIC" -n || die "clearing $TOPIC failed"
    sleep 1
    out=$(retained_any)
    [ -z "$out" ] || die "something is still retained on homeassistant/device/#"
    log "empty retained publish on $TOPIC; 3 s read of homeassistant/device/#: nothing retained"
    ;;

  restart) # step 3 (and the second restart of step 4): graceful restart, 90 s
    log "== graceful restart of ha-a and ha-b ($(now))"
    sleep 10
    stop_both
    start_both
    log "started $(now); waiting 90 s"
    sleep 90
    ;;

  check) # step 4: check-uat02.sh clean (suffix unset)
    log "== check-uat02.sh clean ($(now))"
    out=$("$HT/bin/check-uat02.sh" clean 2>&1)
    rc=$?
    echo "$out" | sed "s|$(git rev-parse --show-toplevel)/||" | tee -a "$C"
    log "exit code: $rc"
    exit $rc
    ;;

  restore) # step 4 fallback: the four registry files of the pre-observation copy, both instances stopped
    pre=$(cat "$S/pre-copy-path") || die "no pre-observation copy recorded"
    [ -d "$pre/a" ] && [ -d "$pre/b" ] || die "pre-observation copy $pre is incomplete"
    log "== fallback: restore the pre-observation registry copy ($(now))"
    stop_both
    for l in "${LETTERS[@]}"; do
      cp -p "$pre/$l/core.entity_registry" "$pre/$l/core.device_registry" "$HT/$l/.storage/" || die "restore of ha-$l failed"
      log "ha-$l: core.entity_registry and core.device_registry copied back from $(basename "$pre")/$l"
    done
    out=$(retained_any)
    [ -z "$out" ] || die "something is retained on homeassistant/device/# before the start"
    log "nothing retained on homeassistant/device/# before the start"
    start_both
    log "started $(now); waiting 90 s"
    sleep 90
    ;;

  final) # step 5: the always-run checks
    log "== step 5 final checks ($(now))"
    for chk in "check-uat04.sh clean" "check-preflight.sh --quick"; do
      # shellcheck disable=SC2086
      out=$("$HT/bin/"$chk 2>&1)
      rc=$?
      echo "$out" | sed "s|$(git rev-parse --show-toplevel)/||" | tee -a "$C"
      log "$chk exit code: $rc"
    done
    out=$(retained_any)
    if [ -z "$out" ]; then log "retained on homeassistant/device/#: none"; else log "retained on homeassistant/device/#: PRESENT"; fi
    for l in "${LETTERS[@]}"; do
      n=$(jq --arg n "$NAME" '[(.data.entities[], .data.deleted_entities[]) | select(.name? == $n)] | length' \
        "$HT/$l/.storage/core.entity_registry")
      log "ha-$l: entries and deleted records named \"$NAME\" in the registry file: $n"
    done
    log "ha-c running: $(podman inspect ha-c --format '{{.State.Running}}')"
    log "mosquitto_sub processes: $(pgrep -c mosquitto_sub || true)"
    ;;

  *)
    echo "usage: cleanup-cr01.sh reset | clear | restart | check | restore | final" >&2
    exit 2
    ;;
esac
