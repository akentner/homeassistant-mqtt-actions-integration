#!/usr/bin/env bash
# Restore the failing tombstone state of UAT-04 before its re-run. Phase 8, plan 08-18.
#   reseed-tombstones.sh --check   read-only: per instance the mqtt-platform deleted-entity records of the two regression ids
#                                  (fixed fields only), the count of live mqtt rows and a line "would flip: ..." or
#                                  "nothing to flip"; changes nothing
#   reseed-tombstones.sh           stop ha-a and ha-b gracefully, back up both core.entity_registry files, require zero live mqtt
#                                  rows, set disabled_by of the EXISTING deleted-entity records of the Lampe Test switch and the
#                                  Bar Select select to null (jq, temporary file, written back over the original: same inode and
#                                  mode), validate every file (restore the copy on any mismatch), start both, run
#                                  check-preflight.sh --quick and check-uat02.sh clean, append everything to
#                                  uat-04-rerun2/prepare.txt
# Why: on the receiver-guard build the replay of UAT-02 makes the guard disable a replayed row before the catch removes it, so
# the tombstones of the first run (disabled_by null) become disabled_by integration. A pass of UAT-04 from that state would prove
# nothing about the receiver. The script restores the precondition of the first run; it makes the check harder, never easier. A
# missing record is an ABORT, a record is never fabricated.
# Run from inside the checkout that holds the evidence. Exit: 0 done, 2 ABORT (bench problem, never a result).
set -euo pipefail
HT="$HOME/ha-test"
# clean reads the baselines of the recorded run (uat-02/), never a suffixed folder
unset PHASE8_EV_SUFFIX
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"

ER="$(evidence_root)"
PREP="$ER/uat-04-rerun2/prepare.txt"
ID_SWITCH=11111111-aaaa-4aaa-8aaa-000000000001 # Lampe Test
ID_SELECT=b6bd2c0e-6d81-49ea-8025-4bd087bd718a # Bar Select
mkdir -p "$ER/uat-04-rerun2"

MODIFIED=0
BK=""
abort() {
  echo "ABORT: $*" >&2
  echo "ABORT: $*" >>"$PREP"
  # leave the bench running again: put the copies back when a file was already written, then start both
  if [ "$MODIFIED" -eq 1 ] && [ -n "$BK" ]; then
    for l in a b; do cat "$BK/$l/core.entity_registry" >"$(inst_dir $l)/.storage/core.entity_registry"; done
    echo "restored the copies of core.entity_registry from $BK" | tee -a "$PREP" >&2
  fi
  if [ "$(podman inspect ha-a --format '{{.State.Running}}')" = false ] || [ "$(podman inspect ha-b --format '{{.State.Running}}')" = false ]; then
    podman start ha-a ha-b >/dev/null 2>&1 || true
  fi
  exit 2
}
say() { echo "$*" | tee -a "$PREP"; }

reg() { echo "$(inst_dir "$1")/.storage/core.entity_registry"; }

# records of the regression ids: platform mqtt, unique id, entity domain prefix, disabled_by value filter (null|any)
count_rec() { # count_rec LETTER ID PREFIX FILTER
  jq --arg id "$2" --arg p "$3" --arg f "$4" \
    '[.data.deleted_entities[] | select(.platform=="mqtt" and .unique_id==$id and (.entity_id|startswith($p)) and ($f=="any" or .disabled_by==null))] | length' "$(reg "$1")"
}
live_mqtt() { jq '[.data.entities[] | select(.platform=="mqtt")] | length' "$(reg "$1")"; }
project() { # project LABEL
  local l
  say "== projection $1 $(date -u +%FT%TZ)"
  for l in a b; do
    say "-- ha-$l deleted mqtt records of the regression ids (entity_id, unique_id, disabled_by); live mqtt rows: $(live_mqtt $l)"
    jq -c --arg s "$ID_SWITCH" --arg e "$ID_SELECT" \
      '[.data.deleted_entities[] | select(.platform=="mqtt" and (.unique_id==$s or .unique_id==$e)) | {entity_id, unique_id, disabled_by}] | sort_by(.entity_id, .unique_id) | .[]' \
      "$(reg $l)" | sed 's/^/  /' | tee -a "$PREP"
  done
}
flip_list() { # which records would change: prints "ha-x switch|select (disabled_by now)" lines, empty when nothing
  local l
  for l in a b; do
    jq -r --arg l "$l" --arg s "$ID_SWITCH" --arg e "$ID_SELECT" '
      .data.deleted_entities[]
      | select(.platform=="mqtt" and ((.unique_id==$s and (.entity_id|startswith("switch."))) or (.unique_id==$e and (.entity_id|startswith("select.")))) and .disabled_by!=null)
      | "ha-\($l) \(.entity_id) (disabled_by \(.disabled_by))"' "$(reg $l)"
  done
}

case "${1:-}" in
  --check)
    project "(--check, read-only)"
    fl=$(flip_list)
    if [ -n "$fl" ]; then
      say "would flip to disabled_by null: $(tr '\n' ';' <<<"$fl")"
    else
      say "nothing to flip"
    fi
    exit 0
    ;;
  "") ;;
  *)
    echo "usage: reseed-tombstones.sh [--check]" >&2
    exit 2
    ;;
esac

"$here/check-preflight.sh" --quick >/dev/null || abort "check-preflight.sh --quick does not print PASS"
say "== restoration of the failing tombstone state (reseed-tombstones.sh) $(date -u +%FT%TZ)"
podman stop -t 60 ha-a ha-b >/dev/null 2>&1 || true
for c in ha-a ha-b; do
  [ "$(podman inspect "$c" --format '{{.State.Running}}')" = false ] || abort "$c is still running after the stop"
done
say "ha-a and ha-b stopped; registry files are flushed"
project "before the restoration"

base=$(cat "$HT/.current-backup-gap08-rerun2" 2>/dev/null) || abort "no pointer ~/ha-test/.current-backup-gap08-rerun2"
[ -d "$base" ] || abort "backup base $base is missing"
BK="$base/reseed-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BK/a" "$BK/b"
chmod 0700 "$BK" "$BK/a" "$BK/b"
for l in a b; do cp -p "$(reg $l)" "$BK/$l/core.entity_registry"; done
say "backup of both core.entity_registry files: $BK"

for l in a b; do
  [ "$(live_mqtt $l)" -eq 0 ] || abort "ha-$l holds live mqtt rows ($(live_mqtt $l)); the restoration needs none"
  for spec in "$ID_SWITCH switch." "$ID_SELECT select."; do
    read -r id pre <<<"$spec"
    n=$(count_rec "$l" "$id" "$pre" any)
    [ "$n" -eq 1 ] || abort "ha-$l: expected exactly one mqtt deleted-entity record for $id with entity id prefix $pre, found $n (a missing record is never fabricated)"
  done
done
say "precondition holds: zero live mqtt rows on both, exactly one record per regression id on both"

# the flip: jq into a temporary file, written back over the original (same inode and mode)
for l in a b; do
  f=$(reg $l)
  tmp=$(mktemp)
  jq --arg s "$ID_SWITCH" --arg e "$ID_SELECT" '
    .data.deleted_entities |= map(
      if .platform=="mqtt" and ((.unique_id==$s and (.entity_id|startswith("switch."))) or (.unique_id==$e and (.entity_id|startswith("select."))))
      then .disabled_by = null else . end)' "$f" >"$tmp" || {
    rm -f "$tmp"
    abort "jq failed on ha-$l"
  }
  MODIFIED=1
  cat "$tmp" >"$f"
  rm -f "$tmp"
done

# validation against the copies; any mismatch restores the copies and ends in ABORT
for l in a b; do
  f=$(reg $l)
  c="$BK/$l/core.entity_registry"
  jq -e . "$f" >/dev/null 2>&1 || abort "ha-$l: the result is not valid JSON"
  [ "$(jq -S -c '.data.entities | sort_by(.entity_id, .unique_id)' "$f" | sha256sum)" = "$(jq -S -c '.data.entities | sort_by(.entity_id, .unique_id)' "$c" | sha256sum)" ] ||
    abort "ha-$l: .data.entities differs from the copy"
  [ "$(jq '.data.deleted_entities | length' "$f")" = "$(jq '.data.deleted_entities | length' "$c")" ] || abort "ha-$l: the count of deleted entities changed"
  # every record other than the two targets is identical; the targets differ only in disabled_by
  istarget='(.platform=="mqtt" and ((.unique_id==$s and (.entity_id|startswith("switch."))) or (.unique_id==$e and (.entity_id|startswith("select.")))))'
  [ "$(jq -S -c --arg s "$ID_SWITCH" --arg e "$ID_SELECT" "[.data.deleted_entities[] | select($istarget | not)] | sort_by(.entity_id, .unique_id, .platform)" "$f" | sha256sum)" = \
    "$(jq -S -c --arg s "$ID_SWITCH" --arg e "$ID_SELECT" "[.data.deleted_entities[] | select($istarget | not)] | sort_by(.entity_id, .unique_id, .platform)" "$c" | sha256sum)" ] ||
    abort "ha-$l: a deleted-entity record other than the two targets differs from the copy"
  [ "$(jq -S -c --arg s "$ID_SWITCH" --arg e "$ID_SELECT" "[.data.deleted_entities[] | select($istarget) | del(.disabled_by)] | sort_by(.entity_id)" "$f" | sha256sum)" = \
    "$(jq -S -c --arg s "$ID_SWITCH" --arg e "$ID_SELECT" "[.data.deleted_entities[] | select($istarget) | del(.disabled_by)] | sort_by(.entity_id)" "$c" | sha256sum)" ] ||
    abort "ha-$l: a target record differs from the copy in a field other than disabled_by"
  [ "$(jq -S -c 'del(.data.entities, .data.deleted_entities)' "$f" | sha256sum)" = "$(jq -S -c 'del(.data.entities, .data.deleted_entities)' "$c" | sha256sum)" ] ||
    abort "ha-$l: the file differs from the copy outside the two record lists"
done
say "validation passed on both files (valid JSON, entities identical, deleted-entity count unchanged, other records identical, targets differ only in disabled_by)"
project "after the restoration (files, instances still stopped)"

sw_a=$(count_rec a "$ID_SWITCH" switch. null)
se_a=$(count_rec a "$ID_SELECT" select. null)
sw_b=$(count_rec b "$ID_SWITCH" switch. null)
se_b=$(count_rec b "$ID_SELECT" select. null)
la=$(live_mqtt a)
lb=$(live_mqtt b)

podman start ha-a ha-b >/dev/null
wait_http 8123 || abort "ha-a did not come up"
wait_http 8124 || abort "ha-b did not come up"
MODIFIED=0
say "both started again on the restored registries"
"$here/check-preflight.sh" --quick | tee -a "$PREP" || abort "check-preflight.sh --quick does not print PASS after the restoration"
"$here/check-uat02.sh" clean | tee -a "$PREP" || abort "check-uat02.sh clean does not print PASS after the restoration"

if [ "$sw_a" -eq 1 ] && [ "$se_a" -eq 1 ] && [ "$sw_b" -eq 1 ] && [ "$se_b" -eq 1 ] && [ "$la" -eq 0 ] && [ "$lb" -eq 0 ]; then
  say "regression state before UAT-04: ha-a null tombstones switch=$sw_a select=$se_a; ha-b null tombstones switch=$sw_b select=$se_b; live mqtt rows a=$la b=$lb"
else
  abort "regression state not reached: ha-a switch=$sw_a select=$se_a; ha-b switch=$sw_b select=$se_b; live mqtt rows a=$la b=$lb"
fi
