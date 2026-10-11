#!/usr/bin/env bash
# Straggler instance gate (Phase 8, plan 08-05).
#   check-hac.sh identity   every .py file of the mounted folder equals `git show v0.1.0:...`, manifest version 0.1.0
#                           (also writes uat-01/v010-identity.txt when run from inside the checkout)
#   check-hac.sh ready      ha-c Up, identity, mqtt and mqtt_actions loaded, availability online, heartbeat heard,
#                           marker approved, no marker line in ha-c's log, quick preflight PASS for the native fleet
#   check-hac.sh stopped    ha-c container down and its retained availability is not online
# Exit 0 PASS, 1 FAIL.
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"
G="$here/ha-test-guard"
V010="$HT/v010/custom_components/mqtt_actions"
mode=${1:-}
case "$mode" in identity | ready | stopped) ;; *)
  echo "usage: check-hac.sh identity|ready|stopped" >&2
  exit 2
  ;;
esac

running() { [ "$(podman inspect ha-c --format '{{.State.Running}}' 2>/dev/null)" = true ]; }

do_identity() {
  local out f want got n=0 top
  top=$(git rev-parse --show-toplevel 2>/dev/null || true)
  out=$(mktemp)
  {
    echo "straggler component identity against git tag v0.1.0 (sha256 of each .py file)"
    echo "tag commit: $(git rev-parse 'v0.1.0^{commit}' 2>/dev/null || echo unknown)"
    echo "mounted source: ~/ha-test/v010/custom_components/mqtt_actions"
  } >"$out"
  for f in "$V010"/*.py; do
    f=$(basename "$f")
    want=$(git show "v0.1.0:custom_components/mqtt_actions/$f" 2>/dev/null | sha256sum | cut -d' ' -f1)
    got=$(sha256sum "$V010/$f" | cut -d' ' -f1)
    n=$((n + 1))
    if [ "$want" = "$got" ] && [ "$want" != e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 ]; then
      echo "equal  $got  $f" >>"$out"
    else
      echo "DIFFERS $f (tag $want, mounted $got)" >>"$out"
      chk_fail "$f differs from v0.1.0"
    fi
  done
  # every tracked .py file of the tag must exist in the mount, too
  while read -r f; do
    [ -f "$V010/${f##*/}" ] || { echo "MISSING $f" >>"$out"; chk_fail "$f missing in the mounted folder"; }
  done < <(git ls-tree --name-only -r v0.1.0 -- custom_components/mqtt_actions | grep '\.py$')
  ver=$(jq -r '.version' "$V010/manifest.json")
  echo "manifest version: $ver" >>"$out"
  [ "$ver" = 0.1.0 ] || chk_fail "manifest version is $ver"
  echo "files compared: $n" >>"$out"
  # a running container must see the same bytes
  if running; then
    local k
    k=$(podman exec ha-c sha256sum /config/custom_components/mqtt_actions/manager.py | cut -d' ' -f1)
    [ "$k" = "$(sha256sum "$V010/manager.py" | cut -d' ' -f1)" ] && echo "container view of manager.py: equal" >>"$out" || chk_fail "container sees another manager.py"
  fi
  [ -n "$top" ] && cp "$out" "$(evidence_root)/uat-01/v010-identity.txt" 2>/dev/null || {
    mkdir -p "$(evidence_root)/uat-01" && cp "$out" "$(evidence_root)/uat-01/v010-identity.txt"
  }
  rm -f "$out"
}

av_of() { probe_sub -t "mqtt_actions/v1/instances/$1/availability" -C 1 -W 4 2>/dev/null || true; }

case "$mode" in
  identity)
    do_identity
    chk_finish "check-hac identity" "uat-01/v010-identity.txt"
    ;;
  ready)
    running || chk_fail "ha-c is not Up"
    do_identity
    if running; then
      iid=$(inst_id c)
      [ -n "$iid" ] || chk_fail "no ha-c instance id"
      st=$("$G" c ws raw config_entries/get 2>/dev/null | jq -r '[.result[] | select(.domain=="mqtt" or .domain=="mqtt_actions") | "\(.domain)=\(.state)"] | sort | join(" ")')
      [ "$st" = "mqtt=loaded mqtt_actions=loaded" ] || chk_fail "entries: ${st:-none}"
      [ "$(av_of "$iid")" = online ] || chk_fail "availability of ha-c is not online"
      [ -n "$(probe_sub -t "mqtt_actions/v1/instances/$iid/heartbeat" -C 1 -W 45 2>/dev/null || true)" ] || chk_fail "no heartbeat from ha-c within 45 s"
      MARKER_ID=$(sed -n 's/^MARKER_ID=//p' "$HT/.fixtures.env" | head -n1)
      n=$("$G" c ws raw repairs/list_issues 2>/dev/null | jq -r --arg id "approval_$MARKER_ID" '[.result.issues[] | select(.issue_id==$id)] | length')
      [ "$n" = 0 ] || chk_fail "the marker is not approved on ha-c (pending issues: ${n:-?})"
      c=$(grep -c "UAT03-MARKER" "$HT/c/home-assistant.log" 2>/dev/null || true)
      [ "${c:-0}" -eq 0 ] || chk_fail "$c marker line(s) in the log of ha-c"
    fi
    "$here/check-preflight.sh" --quick >/dev/null 2>&1 || chk_fail "quick preflight of the native fleet failed"
    chk_finish "check-hac ready" "ha-c"
    ;;
  stopped)
    running && chk_fail "ha-c is still running"
    iid=$(inst_id c)
    [ -n "$iid" ] || chk_fail "no ha-c instance id"
    a=$(av_of "$iid")
    [ "$a" != online ] || chk_fail "retained availability of ha-c still reads online"
    chk_finish "check-hac stopped" "availability: ${a:-empty}"
    ;;
esac
