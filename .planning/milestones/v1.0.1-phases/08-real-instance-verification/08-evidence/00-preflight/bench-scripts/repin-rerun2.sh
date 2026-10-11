#!/usr/bin/env bash
# Re-pin the build under test to the receiver-guard build (D-03). Phase 8, plan 08-18 (receiver-side guard of plan 08-17).
#   repin-rerun2.sh    stop ha-a and ha-b gracefully, project the state before from the flushed registry files, back up both
#                      entity and device registries, keep build.txt as build-caf2fe5d.txt, start both (they load the new code
#                      and run the replay catch: this start is also the cleanup restart of the 08-13 leftovers), wait for the
#                      settle time, rewrite build.txt (previous_sha, first_sha) and mount-hashes.txt, run check-preflight.sh
#                      --quick, project the state after; everything is appended to uat-04-rerun2/prepare.txt
# Run from inside the checkout that holds the evidence (the mount source). mosq is never touched here.
# Exit: 0 done, 2 ABORT (bench problem, nothing is recorded as a result).
set -euo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"

ER="$(evidence_root)"
EV="$ER/00-preflight"
PREP="$ER/uat-04-rerun2/prepare.txt"
PREV_SHA=caf2fe5dc003ea834104f4016d1996be4132e0c8
FIRST_SHA=b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
# the settle time of check-uat02.sh (HA startup plus the quiet period of the replay catch, with margin)
SETTLE=$(sed -n 's/^SETTLE_SECONDS=\([0-9][0-9]*\).*/\1/p' "$here/check-uat02.sh" | head -n1)
[ -n "$SETTLE" ] || SETTLE=90
mkdir -p "$ER/uat-04-rerun2"

abort() {
  echo "ABORT: $*" >&2
  echo "ABORT: $*" >>"$PREP"
  exit 2
}
say() { echo "$*" | tee -a "$PREP"; }

# project LABEL : fixed fields only, from the registry files (flushed when the instance is stopped)
project() {
  local label=$1 l f
  say "== state $label $(date -u +%FT%TZ)"
  for l in a b; do
    f="$(inst_dir $l)/.storage/core.entity_registry"
    say "-- ha-$l live rows with platform mqtt (entity_id, unique_id, disabled_by), $(jq '[.data.entities[] | select(.platform=="mqtt")] | length' "$f") in total"
    jq -c '[.data.entities[] | select(.platform=="mqtt") | {entity_id, unique_id, disabled_by}] | sort_by(.entity_id, .unique_id) | .[]' "$f" | sed 's/^/  /' | tee -a "$PREP"
    say "-- ha-$l deleted entities with platform mqtt (entity_id, unique_id, disabled_by), $(jq '[.data.deleted_entities[] | select(.platform=="mqtt")] | length' "$f") in total"
    jq -c '[.data.deleted_entities[] | select(.platform=="mqtt") | {entity_id, unique_id, disabled_by}] | sort_by(.entity_id, .unique_id) | .[]' "$f" | sed 's/^/  /' | tee -a "$PREP"
    say "-- ha-$l devices with an identifier (mqtt, mqtt_actions_*): $(jq '[.data.devices[] | select(any(.identifiers[]; .[0]=="mqtt" and (.[1] | startswith("mqtt_actions_"))))] | length' "$(inst_dir $l)/.storage/core.device_registry")"
  done
}

pin || abort "cannot pin the mount-source checkout"
rec=$(sed -n 's/^sha: //p' "$EV/build.txt" | head -n1)
[ "$rec" = "$PREV_SHA" ] || abort "build.txt names $rec, expected the previous pin $PREV_SHA (already re-pinned?)"
if ! diffs=$(mount_clean); then abort "mounted custom_components differs from $PIN_SHA: $diffs"; fi

say "== re-pin (repin-rerun2.sh) $(date -u +%FT%TZ)"
say "previous sha: $PREV_SHA"
say "first sha: $FIRST_SHA"
say "new sha: $PIN_SHA ($PIN_BRANCH), commit_time $PIN_COMMIT_TIME"
say "mount: byte-identical to the custom_components tree of the new sha (mount_clean)"
for old in "$PREV_SHA" "$FIRST_SHA"; do
  say "git diff --stat $old $PIN_SHA -- custom_components:"
  git diff --stat "$old" "$PIN_SHA" -- custom_components | sed 's/^/  /' | tee -a "$PREP"
  names=$(git diff --name-only "$old" "$PIN_SHA" -- custom_components | sort | tr '\n' ' ')
  [ "$names" = "custom_components/mqtt_actions/manager.py custom_components/mqtt_actions/takeover.py " ] ||
    abort "the product diff against $old names files other than manager.py and takeover.py: $names"
done
say "product diff against both earlier pins names only manager.py and takeover.py: yes"

podman stop -t 60 ha-a ha-b >/dev/null 2>&1 || true
for c in ha-a ha-b; do
  [ "$(podman inspect "$c" --format '{{.State.Running}}')" = false ] || abort "$c is still running after the stop"
done
say "ha-a and ha-b stopped; registry files are flushed (read below)"

project "before the re-pin"

# backup of both entity and device registries, outside the repo, mode 0700
stamp=$(date -u +%Y%m%dT%H%M%SZ)
BK="$HT/_backup-pre-gap-rerun2-$stamp"
mkdir -p "$BK/a" "$BK/b"
chmod 0700 "$BK" "$BK/a" "$BK/b"
for l in a b; do
  for f in core.entity_registry core.device_registry; do
    cp -p "$(inst_dir $l)/.storage/$f" "$BK/$l/$f"
  done
done
echo "$BK" >"$HT/.current-backup-gap08-rerun2"
say "backup of core.entity_registry and core.device_registry of ha-a and ha-b: $BK (pointer ~/ha-test/.current-backup-gap08-rerun2)"

[ -f "$EV/build-caf2fe5d.txt" ] || cp "$EV/build.txt" "$EV/build-caf2fe5d.txt"
say "kept the previous record as 00-preflight/build-caf2fe5d.txt (the first record stays as build-b7f52b34.txt)"

podman start ha-a ha-b >/dev/null
wait_http 8123 || abort "ha-a did not come up"
wait_http 8124 || abort "ha-b did not come up"
say "both answer; waiting ${SETTLE}s for the replay catch and the start-up work (this start is the cleanup restart)"
sleep "$SETTLE"

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
  echo "previous_sha: $PREV_SHA"
  echo "first_sha: $FIRST_SHA"
  echo "repin_reason: receiver-side guard of plan 08-17 (D-03)"
} >"$EV/build.txt"
{
  for l in a b; do
    for f in manager.py takeover.py const.py document.py; do
      read -r h k < <(mount_hashes $l $f)
      printf 'ha-%s %s host=%s container=%s %s\n' "$l" "$f" "${h:0:16}" "${k:0:16}" "$([ "$h" = "$k" ] && echo match || echo DIFFER)"
    done
  done
} >"$EV/mount-hashes.txt"
say "new build.txt:"
sed 's/^/  /' "$EV/build.txt" | tee -a "$PREP"
say "new mount-hashes.txt:"
sed 's/^/  /' "$EV/mount-hashes.txt" | tee -a "$PREP"
grep -q DIFFER "$EV/mount-hashes.txt" && abort "host and container hashes differ after the start"

"$here/check-preflight.sh" --quick | tee -a "$PREP"

# the registry files are only flushed on stop; the state after the cleanup is read from a read-only look at the running files
# and settled by the caller's own check-uat02.sh clean (live registry, same files)
project "after the re-pin and the settle time (running files, read-only)"
