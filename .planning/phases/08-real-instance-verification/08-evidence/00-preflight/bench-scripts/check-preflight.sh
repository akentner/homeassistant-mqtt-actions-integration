#!/usr/bin/env bash
# Read-only assertions of the pinned build, the mount integrity, the guard and the broker round trip (Phase 8 bench gate).
#   check-preflight.sh            full: includes the guard routing proof and a 55 s heartbeat listen
#   check-preflight.sh --quick    wave gate for later plans: no routing proof, 40 s heartbeat listen
# Run from inside the checkout that holds the evidence. Output: PASS plus the evidence path, or FAIL/ABORT plus the reason.
# Exit: 0 PASS, 1 FAIL, 2 ABORT (bench problem, never a UAT result).
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"

quick=0
[ "${1:-}" = "--quick" ] && quick=1
EV="$(evidence_root)/00-preflight"
ID_A=$(inst_id a)
ID_B=$(inst_id b)
ABORT_MSG=""

# ---- evidence files -------------------------------------------------------------------------------------------------
for f in build.txt mount-hashes.txt heartbeats.txt retained-snapshot.txt registry-baseline-a.json \
  registry-baseline-b.json acl-after.txt backup-manifest.txt; do
  [ -s "$EV/$f" ] || chk_fail "evidence file missing or empty: 00-preflight/$f"
done

# ---- the pinned build ------------------------------------------------------------------------------------------------
if pin; then
  rec=$(sed -n 's/^sha: //p' "$EV/build.txt" 2>/dev/null | head -n1)
  # Compare the integration tree, not the commit: planning-only commits move HEAD without changing the build under test.
  rec_tree=$(git rev-parse "$rec:custom_components" 2>/dev/null || echo "")
  pin_tree=$(git rev-parse "$PIN_SHA:custom_components" 2>/dev/null || echo "")
  { [ -n "$rec_tree" ] && [ "$rec_tree" = "$pin_tree" ]; } ||
    chk_fail "custom_components tree of build.txt sha ($rec) differs from the mounted checkout HEAD ($PIN_SHA)"
  if ! diffs=$(mount_clean); then chk_fail "mounted custom_components is not clean against $PIN_SHA: $(tr '\n' ' ' <<<"$diffs")"; fi
  PIN_COMMIT_TIME=$(git log -1 --format=%cI "$PIN_SHA" -- custom_components 2>/dev/null || echo "$PIN_COMMIT_TIME")
  commit_epoch=$(date -d "$PIN_COMMIT_TIME" +%s)
else
  chk_fail "cannot pin the mount-source checkout"
  commit_epoch=0
fi

for l in a b; do
  c=$(inst_container $l)
  running=$(podman inspect "$c" --format '{{.State.Running}}' 2>/dev/null || echo false)
  [ "$running" = true ] || chk_fail "$c is not Up"
  started=$(podman inspect "$c" --format '{{.State.StartedAt}}' 2>/dev/null | sed -e 's/ m=.*//' -e 's/ [A-Z][A-Z]*$//')
  started_epoch=$(date -d "$started" +%s 2>/dev/null || echo 0)
  [ "$started_epoch" -gt "$commit_epoch" ] || chk_fail "$c StartedAt ($started) is not later than the commit time ($PIN_COMMIT_TIME)"
  for f in manager.py takeover.py const.py document.py; do
    read -r h k < <(mount_hashes $l $f)
    { [ -n "$h" ] && [ "$h" = "$k" ]; } || chk_fail "$c $f: host and container sha256 differ"
  done
done

# mosq must never have been restarted by the bench
want=$(cat "$HT/.mosq-started-before-phase8" 2>/dev/null)
now=$(podman inspect mosq --format '{{.State.StartedAt}}' 2>/dev/null)
[ -n "$want" ] && [ "$want" = "$now" ] || chk_fail "mosq StartedAt changed (was '$want', is '$now')"

# ---- the guard -------------------------------------------------------------------------------------------------------
"$here/ha-test-guard" z --print-target >/dev/null 2>&1 && chk_fail "guard accepted instance letter z"
tgt=$(HA_URL=https://example.invalid HA_TOKEN=x "$here/ha-test-guard" a --print-target 2>/dev/null)
[ "$tgt" = "http://localhost:8123" ] || chk_fail "guard followed an exported HA_URL (printed '$tgt')"
tgt=$("$here/ha-test-guard" b --print-target 2>/dev/null)
[ "$tgt" = "http://localhost:8124" ] || chk_fail "guard maps b to '$tgt'"

if [ "$quick" -eq 0 ]; then
  # Routing proof: an invalid-token login must fail AND leave a new warning in the ha-a log. A call that reached production
  # could not leave that line here. No line means the proof is inconclusive (ABORT).
  logf="$HT/a/home-assistant.log"
  re='Invalid access token|invalid authentication'
  before=$(grep -cE "$re" "$logf" 2>/dev/null || true)
  out=$("$here/ha-test-guard" a --selftest 2>&1)
  rc=$?
  if [ "$rc" -ne 3 ] || ! grep -q 'authentication error' <<<"$out"; then
    chk_fail "guard --selftest did not end in an authentication error (rc=$rc)"
  else
    seen=0
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      after=$(grep -cE "$re" "$logf" 2>/dev/null || true)
      if [ "${after:-0}" -gt "${before:-0}" ]; then
        seen=1
        break
      fi
      sleep 1
    done
    [ "$seen" -eq 1 ] || ABORT_MSG="guard routing proof inconclusive: no new invalid-authentication warning in $logf"
  fi
fi

# ---- broker round trip with a second client --------------------------------------------------------------------------
avail=$(probe_sub -t 'mqtt_actions/v1/instances/+/availability' -F '%t %r %p' -W 3 2>/dev/null || true)
rc_probe=$?
for id in "$ID_A" "$ID_B"; do
  grep -qE "^mqtt_actions/v1/instances/$id/availability 1 online$" <<<"$avail" ||
    chk_fail "probe does not read the retained availability 'online' of $id"
done
bridge_all=$(bridge_sub -t 'mqtt_actions/v1/devices/+/state' -F '%t' -W 3 2>&1)
rc_b=$?
case "$rc_b" in 0 | 27) ;; *) chk_fail "uat_bridge login failed (rc=$rc_b)" ;; esac
bridge_avail=$(bridge_sub -t 'mqtt_actions/v1/instances/+/availability' -F '%t %p' -W 3 2>/dev/null || true)
[ -z "$bridge_avail" ] || chk_fail "uat_bridge can read availability: the edited ACL is not live"

listen=55
[ "$quick" -eq 1 ] && listen=40
hb=$(probe_sub -t 'mqtt_actions/v1/instances/+/heartbeat' -F '%t' -W "$listen" 2>/dev/null || true)
for id in "$ID_A" "$ID_B"; do
  grep -q "/instances/$id/heartbeat" <<<"$hb" || chk_fail "no heartbeat of $id within $listen s"
done
: "$rc_probe" "$bridge_all"

# ---- the evidence tree -----------------------------------------------------------------------------------------------
cl=$("$here/check-evidence-clean.sh" "$EV" 2>&1) || chk_fail "evidence scan: $(tr '\n' ' ' <<<"$cl")"

if [ -n "$ABORT_MSG" ] && [ "${#CHK_FAILS[@]}" -eq 0 ]; then
  echo "ABORT $ABORT_MSG"
  exit 2
fi
chk_finish "preflight$([ "$quick" -eq 1 ] && echo ' (quick)')" "$EV"
