#!/usr/bin/env bash
# Re-pin the build under test after a product change (D-03). Phase 8, plan 08-13 (guard dispositions).
#   repin.sh           stop ha-a and ha-b gracefully, prove the original failing tombstone state is intact from the flushed
#                      registry files, keep build.txt as build-<old sha>.txt, start both (they load the new code), rewrite
#                      build.txt and mount-hashes.txt, run check-preflight.sh --quick; appends to uat-04-rerun/prepare.txt
# Run from inside the checkout that holds the evidence (the mount source). Nothing is pruned: the tombstones are the
# regression state of the guard. mosq is never touched here.
# Exit: 0 done, 2 ABORT (bench problem, nothing is recorded as a result).
set -euo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"

ER="$(evidence_root)"
EV="$ER/00-preflight"
PREP="$ER/uat-04-rerun/prepare.txt"
OLD_SHA=b7f52b34a1e8d6afbf6e1ac75f3b92bbbe54a8f3
ID_SWITCH=11111111-aaaa-4aaa-8aaa-000000000001 # Lampe Test
ID_SELECT=b6bd2c0e-6d81-49ea-8025-4bd087bd718a # Bar Select
mkdir -p "$ER/uat-04-rerun"

abort() {
  echo "ABORT: $*" >&2
  echo "ABORT: $*" >>"$PREP"
  exit 2
}
say() { echo "$*" | tee -a "$PREP"; }

pin || abort "cannot pin the mount-source checkout"
rec=$(sed -n 's/^sha: //p' "$EV/build.txt" | head -n1)
[ "$rec" = "$OLD_SHA" ] || abort "build.txt names $rec, expected the first pin $OLD_SHA (already re-pinned?)"
if ! diffs=$(mount_clean); then abort "mounted custom_components differs from $PIN_SHA: $diffs"; fi

say "== re-pin (repin.sh) $(date -u +%FT%TZ)"
say "old sha: $OLD_SHA"
say "new sha: $PIN_SHA ($PIN_BRANCH), commit_time $PIN_COMMIT_TIME"
say "mount: byte-identical to the custom_components tree of the new sha (mount_clean)"
stat=$(git diff --stat "$OLD_SHA" "$PIN_SHA" -- custom_components)
say "git diff --stat $OLD_SHA $PIN_SHA -- custom_components:"
sed 's/^/  /' <<<"$stat" | tee -a "$PREP"
names=$(git diff --name-only "$OLD_SHA" "$PIN_SHA" -- custom_components | sort | tr '\n' ' ')
[ "$names" = "custom_components/mqtt_actions/manager.py custom_components/mqtt_actions/takeover.py " ] ||
  abort "the product diff names files other than manager.py and takeover.py: $names"
say "product diff names only manager.py and takeover.py (the files plan 08-12 changed): yes"

podman stop -t 60 ha-a ha-b >/dev/null 2>&1 || true
for c in ha-a ha-b; do
  [ "$(podman inspect "$c" --format '{{.State.Running}}')" = false ] || abort "$c is still running after the stop"
done
say "ha-a and ha-b stopped; registry files are flushed (read below)"

# original failing state, read from the flushed registry files: mqtt-platform deleted entities, fixed fields only
for l in a b; do
  f="$(inst_dir $l)/.storage/core.entity_registry"
  say "-- ha-$l deleted entities with platform mqtt (entity_id, unique_id, disabled_by), $(jq '[.data.deleted_entities[] | select(.platform=="mqtt")] | length' "$f") in total"
  jq -c '[.data.deleted_entities[] | select(.platform=="mqtt") | {entity_id, unique_id, disabled_by}] | sort_by(.entity_id, .unique_id) | .[]' "$f" | sed 's/^/  /' | tee -a "$PREP"
  say "-- ha-$l live rows with platform mqtt: $(jq '[.data.entities[] | select(.platform=="mqtt")] | length' "$f")"
  sw=$(jq --arg id "$ID_SWITCH" '[.data.deleted_entities[] | select(.platform=="mqtt" and .unique_id==$id and (.entity_id|startswith("switch.")) and .disabled_by==null)] | length' "$f")
  se=$(jq --arg id "$ID_SELECT" '[.data.deleted_entities[] | select(.platform=="mqtt" and .unique_id==$id and (.entity_id|startswith("select.")) and .disabled_by==null)] | length' "$f")
  say "ha-$l original tombstones with disabled_by null: Lampe Test switch $sw, Bar Select select $se"
  [ "$sw" -ge 1 ] && [ "$se" -ge 1 ] || abort "the original failing state is not intact on ha-$l (switch $sw, select $se)"
done
say "original failing state intact on ha-a and ha-b: yes (nothing pruned)"

[ -f "$EV/build-b7f52b34.txt" ] || cp "$EV/build.txt" "$EV/build-b7f52b34.txt"
say "kept the first record as 00-preflight/build-b7f52b34.txt"

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
  echo "previous_sha: $OLD_SHA"
  echo "repin_reason: product guard of plan 08-12 (D-03)"
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
