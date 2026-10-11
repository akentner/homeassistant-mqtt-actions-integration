#!/usr/bin/env bash
# Phase 8 preflight. Two stages, so the logger block can be added with an editor between backup and restart:
#   preflight.sh stage1   pin the build, stop ha-a and ha-b, back up a, b and mosquitto, take registry baselines
#   preflight.sh stage2   add the bench broker users, start ha-a and ha-b, record build, mounts, heartbeats, snapshot
# Run from inside the checkout that should receive the evidence. mosq is never restarted (persistence is off).
set -euo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"

EV="$(evidence_root)/00-preflight"
mkdir -p "$EV"
stage=${1:-}

abort() {
  verdict "$EV" ABORT "$@"
  echo "ABORT: $*" >&2
  exit 1
}

case "$stage" in
  stage1)
    pin || abort "cannot pin the mount-source checkout"
    if ! diffs=$(mount_clean); then abort "mounted custom_components differs from $PIN_SHA" "$diffs"; fi
    podman inspect mosq --format '{{.State.StartedAt}}' >"$HT/.mosq-started-before-phase8"
    echo "pinned $PIN_SHA ($PIN_BRANCH), stopping ha-a and ha-b"
    podman stop -t 60 ha-a ha-b >/dev/null
    ts=$(date -u +%Y%m%dT%H%M%SZ)
    bk="$HT/_backup-pre-phase8-$ts"
    mkdir "$bk"
    cp -a "$HT/a" "$HT/b" "$HT/mosquitto" "$bk/"
    echo "$bk" >"$HT/.current-backup-phase8"
    {
      echo "backup: $bk"
      echo "restore: podman stop ha-a ha-b; copy $bk/{a,b,mosquitto} back over $HT with cp -a; podman start ha-a ha-b;"
      echo "         podman kill --signal HUP mosq (never restart mosq: persistence is off)"
      echo "taken_utc: $ts (ha-a and ha-b stopped, mosq running)"
      echo "total: $(du -sh "$bk" | cut -f1)"
      echo "entries (type size name, two levels):"
      find "$bk" -mindepth 1 -maxdepth 2 -printf '%y %s %P\n' | sort -k3
    } >"$EV/backup-manifest.txt"
    reg_rows "$bk/a/.storage/core.entity_registry" >"$EV/registry-baseline-a.json"
    reg_rows "$bk/b/.storage/core.entity_registry" >"$EV/registry-baseline-b.json"
    echo "stage1 done: backup $bk"
    ;;
  stage2)
    pin || abort "cannot pin the mount-source checkout"
    "$here/bench-users.sh" add
    for l in a b; do
      grep -q 'custom_components.mqtt_actions' "$(inst_dir $l)/configuration.yaml" ||
        abort "logger block missing in $(inst_dir $l)/configuration.yaml (add it before stage2)"
    done
    podman start ha-a ha-b >/dev/null
    wait_http 8123 || abort "ha-a did not come up"
    wait_http 8124 || abort "ha-b did not come up"
    {
      echo "sha: $PIN_SHA"
      echo "branch: $PIN_BRANCH"
      echo "commit_time: $PIN_COMMIT_TIME"
      [ "$PIN_EXEC_HEAD" != "$PIN_SHA" ] && echo "executing_checkout_head: $PIN_EXEC_HEAD"
      echo "mount_source: $PIN_ROOT/custom_components/mqtt_actions (read-only bind mount on ha-a and ha-b)"
      echo "mount_content: byte-identical to the custom_components tree of sha (blob-by-blob, no extra files)"
      echo "ha_version: $(cat "$HT/a/.HA_VERSION") (a), $(cat "$HT/b/.HA_VERSION") (b)"
      echo "image: $(podman inspect ha-a --format '{{.ImageName}}')"
      echo "started_at_a: $(podman inspect ha-a --format '{{.State.StartedAt}}')"
      echo "started_at_b: $(podman inspect ha-b --format '{{.State.StartedAt}}')"
      echo "instance_id_a: $(inst_id a)"
      echo "instance_id_b: $(inst_id b)"
    } >"$EV/build.txt"
    {
      for l in a b; do
        for f in manager.py takeover.py const.py document.py; do
          read -r h k < <(mount_hashes $l $f)
          printf 'ha-%s %s host=%s container=%s %s\n' "$l" "$f" "${h:0:16}" "${k:0:16}" "$([ "$h" = "$k" ] && echo match || echo DIFFER)"
        done
      done
    } >"$EV/mount-hashes.txt"
    echo "listening 50 s for heartbeats"
    { probe_sub -t 'mqtt_actions/v1/instances/+/heartbeat' -F '%I %t %p' -W 50 || true; } >"$EV/heartbeats.txt"
    { probe_sub -t 'mqtt_actions/#' -t 'homeassistant/#' -t 'mqtt_actions_export/#' -F '%t %r %p' -W 3 || true; } |
      grep -E '^[^ ]+ 1( |$)' | sort >"$EV/retained-snapshot.txt" || true
    cp "$HT/mosquitto/acl" "$EV/acl-after.txt"
    echo "stage2 done: evidence in $EV"
    ;;
  *)
    echo "usage: preflight.sh stage1|stage2" >&2
    exit 2
    ;;
esac
