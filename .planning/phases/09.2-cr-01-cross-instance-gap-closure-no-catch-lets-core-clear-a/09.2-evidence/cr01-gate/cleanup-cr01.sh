#!/usr/bin/env bash
# shellcheck disable=SC2001,SC2015 # `A && B || die` exits in die
# Cleanup and bench hygiene of the CR-01 release gate (plan 09.2-08). Hygiene after the verdict of a variant, never a
# result. Derived from the git-tracked 09.1-evidence/fix2/cr01-observation/cleanup-cr01.sh.
#
#   cleanup-cr01.sh reset | clear | restart | check | restore V | final
#
# Each step appends its time and result to the cleanup.txt of the current variant (the variant of the last
# `cr01-gate.sh pre V`; `restore V` names it). Run from the repository root under ~/ha-test/phase9.2.env with CR01_STATE
# set to the same directory outside the repository as cr01-gate.sh. Exit codes: 0 done or PASS, 1 a check failed,
# 2 ABORT. Holds no secret. Registry changes go through the WebSocket API only, except `restore V`: the recorded D-11
# hygiene restore, which copies the four registry files of the copy taken right before variant V back while ha-a and
# ha-b are stopped.
set -uo pipefail
HT="$HOME/ha-test"
# shellcheck source=/dev/null
. "$HT/bin/lib.sh"
GUARD="$HT/bin/ha-test-guard"
unset PHASE8_EV_SUFFIX

ID=11111111-aaaa-4aaa-8aaa-000000000001
TOPIC="homeassistant/device/$ID/config"
NAME="CR-01 kept button"
SETTLE_SECONDS=90
UNWRAP='(if type == "object" and has("result") then .result else . end)'

abort0() {
  echo "ABORT $*" >&2
  exit 2
}
TOP=$(git rev-parse --show-toplevel 2>/dev/null) || abort0 "run from inside the repository checkout"
[ -n "${CR01_STATE:-}" ] || abort0 "CR01_STATE is not set (a working directory outside the repository is required)"
S=$(cd "$CR01_STATE" 2>/dev/null && pwd -P) || abort0 "CR01_STATE does not exist"
case "$S/" in "$(cd "$TOP" && pwd -P)/"*) abort0 "CR01_STATE ($S) lies inside the repository" ;; esac
G="$(evidence_root)/cr01-gate"
[ -d "$G" ] || abort0 "$G does not exist"

folder() {
  case "$1" in
    3) echo v3-positive-control ;;
    2) echo v2-reverse ;;
    1) echo v1-bench-case ;;
    *) return 1 ;;
  esac
}
if [ "${1:-}" = restore ]; then
  V=${2:-}
else
  V=$(cat "$S/current-variant" 2>/dev/null)
fi
F=$(folder "$V") || abort0 "no variant: give restore 3|2|1, or run cr01-gate.sh pre V first"
C="$G/$F/cleanup.txt"
mkdir -p "$G/$F"

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
run_check() { # run_check SCRIPT ARGS... : logs the output (repository path stripped) and returns the exit code
  local out rc
  out=$("$HT/bin/$1" "${@:2}" 2>&1)
  rc=$?
  sed "s|$TOP/||" <<<"$out" | tee -a "$C"
  log "$* exit code: $rc"
  return $rc
}

[ -s "$C" ] || echo "CR-01 gate cleanup, variant $V ($F): bench hygiene after the verdict, never a result" >>"$C"

case "${1:-}" in
  reset) # name back to null on every live row named NAME on both instances, any platform
    log "== reset the name ($(now))"
    for l in a b; do
      ids=$("$GUARD" "$l" ws raw config/entity_registry/list 2>/dev/null |
        jq -r --arg n "$NAME" "$UNWRAP"' | .[] | select(.name == $n) | .entity_id')
      if [ -z "$ids" ]; then
        log "ha-$l: no live row named \"$NAME\""
        continue
      fi
      for e in $ids; do
        got=$("$GUARD" "$l" ws raw config/entity_registry/update "$(jq -cn --arg e "$e" '{entity_id: $e, name: null}')" 2>/dev/null |
          jq -c "$UNWRAP"' | .entity_entry // . | {entity_id, platform, name, disabled_by}')
        log "ha-$l: reset name of $e, returned ${got:-<no answer>}"
      done
    done
    ;;

  clear) # empty retained publish on TOPIC, read back empty
    log "== clear the topic ($(now))"
    probe_pub -r -q 1 -t "$TOPIC" -n || die "clearing $TOPIC failed"
    sleep 1
    out=$(retained_any)
    [ -z "$out" ] || die "something is still retained on homeassistant/device/#"
    log "empty retained publish on $TOPIC; 3 s read of homeassistant/device/#: nothing retained"
    ;;

  restart) # graceful restart of ha-a and ha-b, 90 s
    log "== graceful restart of ha-a and ha-b ($(now))"
    sleep 10
    stop_both
    start_both
    log "started $(now); waiting $SETTLE_SECONDS s"
    sleep "$SETTLE_SECONDS"
    ;;

  check) # the clean checks: check-uat02.sh clean, check-uat04.sh clean, check-preflight.sh --quick
    log "== clean checks ($(now))"
    bad=0
    run_check check-uat02.sh clean || bad=1
    run_check check-uat04.sh clean || bad=1
    run_check check-preflight.sh --quick || bad=1
    if [ "$bad" -eq 0 ]; then log "clean checks: PASS"; else log "clean checks: FAIL"; fi
    exit "$bad"
    ;;

  restore) # D-11 hygiene restore: the four registry files of the copy taken right before variant V, both stopped
    pre=$(cat "$S/v$V/pre-copy-path" 2>/dev/null) || die "no pre-variant copy recorded for variant $V"
    [ -f "$pre/a/core.entity_registry" ] && [ -f "$pre/b/core.device_registry" ] || die "pre-variant copy of variant $V is incomplete"
    log "== D-11 hygiene restore of the pre-variant copy of variant $V ($(now))"
    out=$(retained_any)
    [ -z "$out" ] || die "something is retained on homeassistant/device/#: run clear first"
    stop_both
    for l in a b; do
      cp -p "$pre/$l/core.entity_registry" "$pre/$l/core.device_registry" "$HT/$l/.storage/" || die "restore of ha-$l failed"
      log "ha-$l: core.entity_registry and core.device_registry copied back from <9.2 backup base>/$(basename "$pre")/$l"
    done
    out=$(probe_sub -t "$TOPIC" -C 1 -W 3 -F '%r' 2>/dev/null)
    [ -z "$out" ] || die "TOPIC holds a retained payload before the start"
    log "TOPIC holds no retained payload before the start"
    start_both
    log "started $(now); waiting $SETTLE_SECONDS s"
    sleep "$SETTLE_SECONDS"
    ;;

  final) # the clean checks, nothing retained, no entity or deleted record named NAME, ha-c stopped, no mosquitto_sub
    log "== final checks ($(now))"
    bad=0
    run_check check-uat02.sh clean || bad=1
    run_check check-uat04.sh clean || bad=1
    run_check check-preflight.sh --quick || bad=1
    out=$(retained_any)
    if [ -z "$out" ]; then
      log "retained on homeassistant/device/#: none"
    else
      log "retained on homeassistant/device/#: PRESENT"
      bad=1
    fi
    for l in a b; do
      n=$(jq --arg n "$NAME" '[(.data.entities[], .data.deleted_entities[]) | select(.name? == $n)] | length' \
        "$HT/$l/.storage/core.entity_registry")
      log "ha-$l: entities and deleted records named \"$NAME\" in the registry file: $n"
      [ "$n" = 0 ] || bad=1
    done
    hc=$(podman inspect ha-c --format '{{.State.Running}}' 2>/dev/null)
    log "ha-c running: ${hc:-unknown}"
    [ "$hc" = false ] || bad=1
    ms=$(pgrep -c mosquitto_sub || true)
    log "mosquitto_sub processes: $ms"
    [ "$ms" = 0 ] || bad=1
    if [ "$bad" -eq 0 ]; then log "final: PASS"; else log "final: FAIL"; fi
    exit "$bad"
    ;;

  *)
    echo "usage: cleanup-cr01.sh reset | clear | restart | check | restore V | final" >&2
    exit 2
    ;;
esac
