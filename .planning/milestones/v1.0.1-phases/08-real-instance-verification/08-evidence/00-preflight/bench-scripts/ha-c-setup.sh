#!/usr/bin/env bash
# Phase 8, plan 08-05 task 2: set up the straggler instance ha-c (v0.1.0 component, own MQTT user and ACL block).
# Resumable: every step is idempotent. Run from inside the evidence checkout (setup.txt etc. go to uat-01).
#   ha-c-setup.sh [--step N]       N = 1..8, without --step all steps run in order
# Secrets (owner password, tokens, broker password) live only in ~/ha-test with mode 0600 and are never printed.
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"
G="$here/ha-test-guard"
EV="$(evidence_root)/uat-01"
mkdir -p "$EV"
PORT=8125
CDIR="$HT/c"
OWNERF="$HT/.ha-c-owner"
TOKF="$HT/.token-c"
V010="$HT/v010/custom_components/mqtt_actions"
IMAGE="ghcr.io/home-assistant/home-assistant:2026.9"
PASSWD="$HT/mosquitto/passwd"
ACL="$HT/mosquitto/acl"

only=""
[ "${1:-}" = "--step" ] && only=${2:-}
want() { [ -z "$only" ] || [ "$only" = "$1" ]; }
die() { echo "ABORT: $*" >&2; exit 2; }
say() { echo "[ha-c-setup] $*" >&2; }
gen_pw() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24 || true; }

c_get() { "$G" c rest GET "$1"; }

# ---- 1 config and deps ---------------------------------------------------------------------------------------------
step1() {
  say "step 1: configuration and deps"
  mkdir -p "$CDIR/custom_components"
  if [ ! -f "$CDIR/configuration.yaml" ]; then
    cat >"$CDIR/configuration.yaml" <<'EOF'
default_config:

http:
  server_port: 8125

# Phase 8 bench: same INFO logger block as ha-a and ha-b
logger:
  default: warning
  logs:
    custom_components.mqtt_actions: info
EOF
  fi
  # T-08-SC: reuse the deps folder of ha-b before the first start
  [ -d "$CDIR/deps" ] || cp -a "$HT/b/deps" "$CDIR/deps"
}

# ---- 2 container and identity --------------------------------------------------------------------------------------
step2() {
  say "step 2: container ha-c"
  if ! podman container exists ha-c; then
    ss -ltn | grep -q ":$PORT " && die "port $PORT is in use"
    podman run -d --name ha-c --network host --restart no -e TZ=Europe/Berlin \
      -v "$CDIR:/config" \
      -v "$V010:/config/custom_components/mqtt_actions:ro" \
      "$IMAGE" >/dev/null || die "podman run failed"
  else
    [ "$(podman inspect ha-c --format '{{.State.Running}}')" = true ] || podman start ha-c >/dev/null
  fi
  "$here/check-hac.sh" identity || die "identity check failed"
  say "waiting for http on $PORT (first start can take minutes)"
  local i
  for ((i = 0; i < 300; i++)); do
    code=$(curl -s -o /dev/null -m 3 -w '%{http_code}' "http://localhost:$PORT/api/" || true)
    case "$code" in 401 | 200 | 404) return 0 ;; esac
    sleep 2
  done
  die "ha-c did not answer within 10 min"
}

# ---- 3 onboarding and token ----------------------------------------------------------------------------------------
step3() {
  say "step 3: onboarding and token"
  if [ -s "$TOKF" ] && [ "$(curl -s -o /dev/null -m 5 -w '%{http_code}' -K <(printf 'header = "Authorization: Bearer %s"\n' "$(tr -d '\r\n' <"$TOKF")") "http://localhost:$PORT/api/")" = 200 ]; then
    say "token already valid, skipping"
    return 0
  fi
  umask 077
  local base="http://localhost:$PORT" cid="http://localhost:$PORT/" resp code access
  if [ ! -f "$OWNERF" ]; then
    printf 'username=ha_c_owner\npassword=%s\n' "$(gen_pw)" >"$OWNERF"
    chmod 600 "$OWNERF"
  fi
  export HAC_USER HAC_PW
  HAC_USER=$(sed -n 's/^username=//p' "$OWNERF")
  HAC_PW=$(sed -n 's/^password=//p' "$OWNERF")
  # which onboarding steps are open
  resp=$(curl -s -m 10 "$base/api/onboarding") || die "onboarding endpoint unreachable"
  say "onboarding state: $(jq -c '[.[] | "\(.step)=\(.done)"]' <<<"$resp" 2>/dev/null || echo unparsable)"
  if [ "$(jq -r '[.[] | select(.step=="user") | .done][0]' <<<"$resp")" = false ]; then
    resp=$(jq -n --arg cid "$cid" '{client_id:$cid, name:"HA Three Owner", username:env.HAC_USER, password:env.HAC_PW, language:"en"}' |
      curl -s -m 30 -X POST -H 'Content-Type: application/json' --data-binary @- "$base/api/onboarding/users") || die "onboarding user call failed"
    code=$(jq -r '.auth_code // empty' <<<"$resp")
    [ -n "$code" ] || die "no auth_code from /api/onboarding/users (needs the owner fallback, see plan)"
  else
    # user exists already (resumed run): log in through the login flow
    resp=$(curl -s -m 20 -X POST -H 'Content-Type: application/json' \
      --data-binary "$(jq -n --arg cid "$cid" '{client_id:$cid, handler:["homeassistant", null], redirect_uri:$cid}')" \
      "$base/auth/login_flow")
    local fid
    fid=$(jq -r '.flow_id // empty' <<<"$resp")
    [ -n "$fid" ] || die "no login flow"
    resp=$(jq -n --arg cid "$cid" '{client_id:$cid, username:env.HAC_USER, password:env.HAC_PW}' |
      curl -s -m 20 -X POST -H 'Content-Type: application/json' --data-binary @- "$base/auth/login_flow/$fid")
    code=$(jq -r '.result // empty' <<<"$resp")
    [ -n "$code" ] || die "login flow gave no code"
  fi
  resp=$(curl -s -m 20 -X POST --data-urlencode grant_type=authorization_code --data-urlencode "code=$code" \
    --data-urlencode "client_id=$cid" "$base/auth/token")
  access=$(jq -r '.access_token // empty' <<<"$resp")
  [ -n "$access" ] || die "no access token from /auth/token"
  # remaining onboarding steps (best effort; a step that is done answers 403)
  local s
  for s in core_config analytics; do
    curl -s -o /dev/null -m 30 -X POST -H "Content-Type: application/json" -K <(printf 'header = "Authorization: Bearer %s"\n' "$access") \
      --data-binary '{}' "$base/api/onboarding/$s" || true
  done
  curl -s -o /dev/null -m 30 -X POST -H "Content-Type: application/json" -K <(printf 'header = "Authorization: Bearer %s"\n' "$access") \
    --data-binary "$(jq -n --arg cid "$cid" '{client_id:$cid, redirect_uri:$cid}')" "$base/api/onboarding/integration" || true
  # the short-lived token goes into the token file only until the long-lived one replaces it (guard stays the only entry)
  printf '%s' "$access" >"$TOKF"
  chmod 600 "$TOKF"
  resp=$("$G" c ws raw auth/long_lived_access_token '{"client_name":"phase8-ha-c","lifespan":365}') || die "long-lived token command failed"
  local llat
  llat=$(jq -r '.result // empty' <<<"$resp")
  [ -n "$llat" ] || die "no long-lived token in the answer"
  printf '%s' "$llat" >"$TOKF"
  chmod 600 "$TOKF"
  "$G" c rest GET /api/ | jq -e '.message' >/dev/null || die "new token does not work"
  say "token written (mode $(stat -c %a "$TOKF")), onboarding steps now: $(curl -s -m 10 "$base/api/onboarding" | jq -c '[.[] | "\(.step)=\(.done)"]')"
}

# ---- 4 broker user and ACL block ----------------------------------------------------------------------------------
step4() {
  say "step 4: broker user ha_three"
  [ -f "$ENVF" ] || die "no env file"
  local orig
  if [ -z "$(_env_get UAT_HA_THREE_PW)" ] || ! cut -d: -f1 "$PASSWD" | grep -qx ha_three; then
    local pw
    pw=$(gen_pw)
    grep -v '^UAT_HA_THREE_PW=' "$ENVF" >"$ENVF.new" || true
    printf 'UAT_HA_THREE_PW=%s\n' "$pw" >>"$ENVF.new"
    mv "$ENVF.new" "$ENVF"
    chmod 600 "$ENVF"
    orig=$(stat -c %a "$PASSWD")
    mosquitto_passwd -b "$PASSWD" ha_three "$pw"
    chmod "$orig" "$PASSWD"
  fi
  if ! grep -qx 'user ha_three' "$ACL"; then
    cp -n "$ACL" "$HT/mosquitto/acl.bak-phase8-05"
    orig=$(stat -c %a "$ACL")
    [ -n "$(tail -c1 "$ACL")" ] && echo >>"$ACL"
    cat >>"$ACL" <<'EOF'

user ha_three
topic readwrite mqtt_actions/v1/devices/+/retrigger
topic readwrite mqtt_actions/v1/instances/+/acks
topic readwrite mqtt_actions/v1/instances/+/heartbeat
topic readwrite mqtt_actions/v1/devices/+/config
topic readwrite mqtt_actions/v1/devices/+/state
topic readwrite mqtt_actions/v1/devices/+/test
topic readwrite homeassistant/#
topic read mqtt_actions/v1/instances/+/availability
EOF
    chmod "$orig" "$ACL"
  fi
  podman kill --signal HUP mosq >/dev/null
}

# ---- 5 MQTT entry --------------------------------------------------------------------------------------------------
entry_state() { # entry_state DOMAIN -> "state" or empty
  "$G" c ws raw config_entries/get | jq -r --arg d "$1" '[.result[] | select(.domain==$d) | .state][0] // empty'
}
step5() {
  say "step 5: mqtt entry on ha-c"
  if [ -n "$(entry_state mqtt)" ]; then say "mqtt entry present: $(entry_state mqtt)"; return 0; fi
  local resp fid body
  resp=$("$G" c rest POST /api/config/config_entries/flow '{"handler":"mqtt","show_advanced_options":true}')
  fid=$(jq -r '.flow_id // empty' <<<"$resp")
  [ -n "$fid" ] || die "no flow id: $(jq -c '{type,reason,message}' <<<"$resp")"
  say "flow step: $(jq -r '.step_id' <<<"$resp") ($(jq -r '.type' <<<"$resp"))"
  # drive up to four steps: fill broker, accept defaults elsewhere
  local n
  for n in 1 2 3 4; do
    case "$(jq -r '.step_id // empty' <<<"$resp")" in
      broker)
        body=$(HAC_PW=$(_env_get UAT_HA_THREE_PW) jq -n '{broker:"localhost", port:1883, username:"ha_three", password:env.HAC_PW, protocol:"5", other_settings:{set_client_cert:false, set_ca_cert:"off", transport:"tcp"}}')
        ;;
      *) body='{}' ;;
    esac
    resp=$("$G" c rest POST "/api/config/config_entries/flow/$fid" "$body")
    say "flow answer: type=$(jq -r '.type' <<<"$resp") step=$(jq -r '.step_id // "-"' <<<"$resp") errors=$(jq -c '.errors // {}' <<<"$resp")"
    [ "$(jq -r '.type' <<<"$resp")" = create_entry ] && break
    [ "$(jq -r '.type' <<<"$resp")" = form ] || break
  done
  [ "$(jq -r '.type' <<<"$resp")" = create_entry ] || die "mqtt flow did not end in create_entry (see the answer above)"
  local i
  for ((i = 0; i < 30; i++)); do [ "$(entry_state mqtt)" = loaded ] && return 0; sleep 2; done
  die "mqtt entry not loaded: $(entry_state mqtt)"
}

write_acl_diff() {
  {
    echo "# diff of the bench ACL for plan 08-05 (before: acl.bak-phase8-05, after: acl); the availability write line names ha-c's own instance id"
    diff "$HT/mosquitto/acl.bak-phase8-05" "$ACL"
  } >"$EV/acl-diff.txt"
}

# ---- 6 hub, ACL line, restart, read back ---------------------------------------------------------------------------
step6() {
  say "step 6: MQTT Actions hub on ha-c"
  local resp fid
  if [ -z "$(entry_state mqtt_actions)" ]; then
    resp=$("$G" c rest POST /api/config/config_entries/flow '{"handler":"mqtt_actions"}')
    fid=$(jq -r '.flow_id // empty' <<<"$resp")
    [ -n "$fid" ] || die "no hub flow: $(jq -c '{type,reason,message}' <<<"$resp")"
    resp=$("$G" c rest POST "/api/config/config_entries/flow/$fid" '{"base_topic":"mqtt_actions","instance_name":"Test HA Three v0.1.0"}')
    [ "$(jq -r '.type' <<<"$resp")" = create_entry ] || die "hub flow did not create the entry: $(jq -c '{type,errors,step_id}' <<<"$resp")"
  fi
  local iid i
  for ((i = 0; i < 30; i++)); do iid=$(inst_id c); [ -n "$iid" ] && break; sleep 2; done
  [ -n "$iid" ] || die "no instance id in core.config_entries"
  say "ha-c instance id: $iid"
  local line="topic write mqtt_actions/v1/instances/$iid/availability"
  cp "$ACL" "$EV/acl-before-ha-three-line.tmp"
  if ! grep -qxF "$line" "$ACL"; then
    local orig
    orig=$(stat -c %a "$ACL")
    # the line belongs to the ha_three block, which is the last block of the file at this point
    python3 - "$ACL" "$line" <<'PY'
import sys
path, line = sys.argv[1], sys.argv[2]
rows = open(path).read().split("\n")
out, inblock, done = [], False, False
for i, row in enumerate(rows):
    if row == "user ha_three":
        inblock = True
    elif inblock and (row.startswith("user ") or row == ""):
        # end of the block: insert the line before leaving it
        if not done:
            out.append(line)
            done = True
        inblock = False
    out.append(row)
if inblock and not done:
    out.append(line)
open(path, "w").write("\n".join(out))
PY
    chmod "$orig" "$ACL"
  fi
  write_acl_diff
  rm -f "$EV/acl-before-ha-three-line.tmp"
  podman kill --signal HUP mosq >/dev/null
  say "restarting ha-c"
  podman restart -t 60 ha-c >/dev/null
  wait_http "$PORT" || die "ha-c did not come back"
  # read back with the second client: availability retained online, heartbeat within 60 s
  local av hb
  for ((i = 0; i < 20; i++)); do
    av=$(probe_sub -t "mqtt_actions/v1/instances/$iid/availability" -C 1 -W 5 2>/dev/null || true)
    [ "$av" = online ] && break
    sleep 3
  done
  hb=$(probe_sub -t "mqtt_actions/v1/instances/$iid/heartbeat" -C 1 -W 60 2>/dev/null || true)
  say "availability read back: ${av:-none}; heartbeat heard: $([ -n "$hb" ] && echo yes || echo no)"
  [ "$av" = online ] && [ -n "$hb" ] || die "second client did not see availability online and a heartbeat (ACL line or reload)"
}

# ---- 7 approve the marker mirror -----------------------------------------------------------------------------------
step7() {
  say "step 7: approve the marker mirror on ha-c"
  local MARKER_ID resp fid i n
  MARKER_ID=$(sed -n 's/^MARKER_ID=//p' "$HT/.fixtures.env" | head -n1)
  [ -n "$MARKER_ID" ] || die "no MARKER_ID"
  for ((i = 0; i < 60; i++)); do
    n=$("$G" c ws raw repairs/list_issues | jq -r --arg id "approval_$MARKER_ID" '[.result.issues[] | select(.issue_id==$id)] | length')
    [ "$n" = 1 ] && break
    sleep 3
  done
  if [ "$n" = 1 ]; then
    resp=$("$G" c rest POST /api/repairs/issues/fix "$(jq -n --arg id "approval_$MARKER_ID" '{handler:"mqtt_actions", issue_id:$id}')")
    fid=$(jq -r '.flow_id // empty' <<<"$resp")
    [ -n "$fid" ] || die "no repairs flow: $(jq -c '{type,message}' <<<"$resp")"
    resp=$("$G" c rest POST "/api/repairs/issues/fix/$fid" '{}')
    say "repairs flow result: $(jq -r '.type' <<<"$resp")"
  else
    say "no pending approval issue for the marker (already approved or not mirrored)"
  fi
  sleep 5
}

# ---- 8 setup.txt ---------------------------------------------------------------------------------------------------
step8() {
  say "step 8: setup.txt"
  write_acl_diff
  local iid MARKER_ID av hb mirrors mk
  iid=$(inst_id c)
  MARKER_ID=$(sed -n 's/^MARKER_ID=//p' "$HT/.fixtures.env" | head -n1)
  av=$(probe_sub -t "mqtt_actions/v1/instances/$iid/availability" -C 1 -W 5 2>/dev/null || true)
  hb=$(probe_sub -t "mqtt_actions/v1/instances/$iid/heartbeat" -C 1 -W 60 2>/dev/null || true)
  mirrors=$("$G" c ws raw get_states | jq -r '[.result[] | select(.entity_id | startswith("switch.") or startswith("select."))] | length')
  mk=$("$G" c ws raw repairs/list_issues | jq -r --arg id "approval_$MARKER_ID" '[.result.issues[] | select(.issue_id==$id)] | length')
  {
    echo "ha-c instance id: $iid"
    echo "ha-c instance name: Test HA Three v0.1.0 (base topic mqtt_actions, hub entry of the v0.1.0 component)"
    echo "image: $IMAGE ($(cat "$CDIR/.HA_VERSION" 2>/dev/null))"
    echo "container started: $(podman inspect ha-c --format '{{.State.StartedAt}}')"
    echo "port: $PORT (host network, TZ Europe/Berlin, restart policy no, not privileged; read from podman inspect ha-b)"
    echo "mounts: ~/ha-test/c as /config; ~/ha-test/v010/custom_components/mqtt_actions read-only over the component folder"
    echo "mqtt user: ha_three (protocol 5), own ACL block with the availability write line for the id above (acl-diff.txt)"
    echo "ACL read-back (second client uat_probe): availability $av, heartbeat $([ -n "$hb" ] && echo heard || echo NOT heard)"
    echo "mqtt entry: $(entry_state mqtt); mqtt_actions entry: $(entry_state mqtt_actions)"
    echo "switch and select entities on ha-c at setup time (count): $mirrors"
    echo "marker mirror approval issue still pending on ha-c: $mk (0 = approved)"
    echo "written: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } >"$EV/setup.txt"
  cat "$EV/setup.txt"
}

# ---- 9 (explicit only) promote the pending HTTP config ---------------------------------------------------------------------
# HA 2026.9 stores the YAML http block as a PENDING config and reverts to the stable one (default port 8123, taken by ha-a)
# with a restart when nobody confirms it within 5 minutes. ha-a and ha-b hold the port as the stable config. Run with the
# container stopped: ha-c-setup.sh --step 9 stops it, promotes pending to stable, starts it again.
step9() {
  say "step 9: promote the pending HTTP config"
  podman stop -t 60 ha-c >/dev/null
  cp -n "$CDIR/.storage/http" "$CDIR/.storage/http.bak-phase8-05"
  jq '.data.stable = (.data.pending | .error = null | .error_message = null) | .data.pending = null' \
    "$CDIR/.storage/http.bak-phase8-05" >"$CDIR/.storage/http.new" && mv "$CDIR/.storage/http.new" "$CDIR/.storage/http"
  podman start ha-c >/dev/null
  wait_http "$PORT"
}

want 1 && step1
want 2 && step2
want 3 && step3
want 4 && step4
want 5 && step5
want 6 && step6
want 7 && step7
want 8 && step8
[ "$only" = 9 ] && step9
exit 0
