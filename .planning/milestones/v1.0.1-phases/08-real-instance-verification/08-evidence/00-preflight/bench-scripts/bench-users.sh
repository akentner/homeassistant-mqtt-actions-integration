#!/usr/bin/env bash
# Throw-away broker users of the Phase 8 bench: uat_probe (reads and writes everything, the independent second client)
# and uat_bridge (same reach as the existing "bridge" user, the external publisher of UAT-03).
#   bench-users.sh add | remove | status
# Never restarts mosq: persistence is off, a restart drops every retained message. The broker reloads passwd and acl on SIGHUP.
set -euo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"

PASSWD="$HT/mosquitto/passwd"
ACL="$HT/mosquitto/acl"

gen_pw() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24 || true; }

reload_broker() { podman kill --signal HUP mosq >/dev/null; }

has_user() { cut -d: -f1 "$PASSWD" | grep -qx "$1"; }
has_acl() { grep -qx "user $1" "$ACL"; }

cmd=${1:-status}
case "$cmd" in
  add)
    umask 077
    [ -f "$ENVF" ] || : >"$ENVF"
    chmod 600 "$ENVF"
    for pair in uat_probe:UAT_PROBE_PW uat_bridge:UAT_BRIDGE_PW; do
      user=${pair%%:*}
      var=${pair##*:}
      if [ -z "$(_env_get "$var")" ] || ! has_user "$user"; then
        pw=$(gen_pw)
        grep -v "^$var=" "$ENVF" >"$ENVF.new" || true
        printf '%s=%s\n' "$var" "$pw" >>"$ENVF.new"
        mv "$ENVF.new" "$ENVF"
        chmod 600 "$ENVF"
        orig_mode=$(stat -c %a "$PASSWD")
        mosquitto_passwd -b "$PASSWD" "$user" "$pw"
        chmod "$orig_mode" "$PASSWD" # the broker runs as another uid inside the container and must still read it
      fi
    done
    orig_mode=$(stat -c %a "$ACL")
    [ -n "$(tail -c1 "$ACL")" ] && echo >>"$ACL"
    if ! has_acl uat_probe; then
      printf '\nuser uat_probe\ntopic readwrite #\n' >>"$ACL"
    fi
    if ! has_acl uat_bridge; then
      printf '\nuser uat_bridge\ntopic readwrite mqtt_actions/v1/devices/+/state\n' >>"$ACL"
    fi
    chmod "$orig_mode" "$ACL"
    reload_broker
    echo "added uat_probe and uat_bridge; env file mode $(stat -c %a "$ENVF")"
    ;;
  remove)
    for user in uat_probe uat_bridge; do
      has_user "$user" && mosquitto_passwd -D "$PASSWD" "$user"
      if has_acl "$user"; then
        # drop the "user X" line and the topic lines after it up to the next blank line or user section
        awk -v u="user $user" '
          $0 == u {skip = 1; next}
          skip && /^user / {skip = 0}
          skip && /^$/ {skip = 0; next}
          !skip {print}' "$ACL" >"$ACL.new"
        cat "$ACL.new" >"$ACL"
        rm -f "$ACL.new"
      fi
    done
    chmod 644 "$PASSWD" "$ACL"
    rm -f "$ENVF"
    reload_broker
    echo "removed uat_probe and uat_bridge"
    ;;
  status)
    for user in uat_probe uat_bridge; do
      echo "$user passwd=$(has_user "$user" && echo yes || echo no) acl=$(has_acl "$user" && echo yes || echo no)"
    done
    echo "env file: $([ -f "$ENVF" ] && stat -c %a "$ENVF" || echo absent)"
    ;;
  *)
    echo "usage: bench-users.sh add|remove|status" >&2
    exit 2
    ;;
esac
