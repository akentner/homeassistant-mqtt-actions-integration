#!/usr/bin/env bash
# Shared bench layer for the Phase 8 real-instance verification. Source it, do not execute it.
# Everything here is read-only unless a function says otherwise. Bench lives outside the repository on purpose:
# it carries local ports and paths.

HT="${HT:-$HOME/ha-test}"
BIN="$HT/bin"
ENVF="$HT/.mqtt-uat.env"
PHASE_DIR_REL=".planning/phases/08-real-instance-verification"

# ---- instance table ------------------------------------------------------------------------------------------------
# letter -> container, port, instance id (c is read from its own config once it exists)
inst_container() { case "$1" in a) echo ha-a ;; b) echo ha-b ;; c) echo ha-c ;; *) return 1 ;; esac; }
inst_port() { case "$1" in a) echo 8123 ;; b) echo 8124 ;; c) echo 8125 ;; *) return 1 ;; esac; }
# ~/ha-test/.instance-ids.env (INSTANCE_ID_A=..., INSTANCE_ID_B=...) wins over the table below. Plan 08-08 re-adds the hub of
# ha-b, which gives ha-b a new instance id (instance ids are not secrets).
_iid_env() { sed -n "s/^INSTANCE_ID_$1=//p" "$HT/.instance-ids.env" 2>/dev/null | head -n1; }
inst_id() {
  local e
  e=$(_iid_env "$(echo "$1" | tr a-z A-Z)")
  if [ -n "$e" ]; then
    echo "$e"
    return 0
  fi
  case "$1" in
    a) echo 3851f34f-fa67-4f3c-bba0-122465013c3d ;;
    b) echo a09499e4-5674-48d5-b3d6-4860d5226fcb ;;
    c) # single non-secret field of the mqtt_actions entry; never dump the whole file
      jq -r '.data.entries[] | select(.domain=="mqtt_actions") | .data.instance_id' \
        "$HT/c/.storage/core.config_entries" 2>/dev/null | head -n1 ;;
    *) return 1 ;;
  esac
}
inst_dir() { case "$1" in a | b | c) echo "$HT/$1" ;; *) return 1 ;; esac; }

# ---- evidence root -------------------------------------------------------------------------------------------------
# Derived from the git toplevel of the checkout the script runs in (a worktree writes into its own tree).
# PHASE8_EVIDENCE_ROOT overrides it for tests.
evidence_root() {
  if [ -n "${PHASE8_EVIDENCE_ROOT:-}" ]; then
    echo "$PHASE8_EVIDENCE_ROOT"
    return
  fi
  local top
  top=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "lib.sh: run from inside a checkout of the repository" >&2
    return 1
  }
  echo "$top/$PHASE_DIR_REL/08-evidence"
}
phase_dir() { echo "$(dirname "$(evidence_root)")"; }

# ---- the build under test ------------------------------------------------------------------------------------------
# The containers bind-mount custom_components/mqtt_actions of ONE checkout. Derive it, never hard-code it.
mount_src() {
  podman inspect ha-a --format '{{range .Mounts}}{{.Source}}{{"\t"}}{{.Destination}}{{"\n"}}{{end}}' |
    awk -F'\t' '$2 ~ /custom_components\/mqtt_actions$/ {print $1; exit}'
}
mount_root() {
  local s
  s=$(mount_src)
  echo "${s%/custom_components/mqtt_actions}"
}

# Resolve HEAD of the mount-source checkout by reading its .git files (read-only, no git call into that tree; the
# object database is shared with the executing checkout, so commit data is read from there).
# Sets PIN_ROOT PIN_BRANCH PIN_SHA PIN_COMMIT_TIME PIN_EXEC_HEAD. Returns non-zero when it cannot be resolved.
pin() {
  PIN_ROOT=$(mount_root)
  [ -n "$PIN_ROOT" ] || {
    echo "pin: no mount of custom_components/mqtt_actions on ha-a" >&2
    return 1
  }
  local gd="$PIN_ROOT/.git" head ref
  [ -d "$gd" ] || {
    echo "pin: $PIN_ROOT/.git is not a directory" >&2
    return 1
  }
  head=$(<"$gd/HEAD")
  if [[ "$head" == "ref: "* ]]; then
    ref=${head#ref: }
    PIN_BRANCH=${ref#refs/heads/}
    if [ -f "$gd/$ref" ]; then
      PIN_SHA=$(<"$gd/$ref")
    else
      PIN_SHA=$(awk -v r="$ref" '$2==r {print $1}' "$gd/packed-refs" 2>/dev/null)
    fi
  else
    PIN_BRANCH="(detached)"
    PIN_SHA=$head
  fi
  [[ "$PIN_SHA" =~ ^[0-9a-f]{40}$ ]] || {
    echo "pin: cannot resolve HEAD of $PIN_ROOT" >&2
    return 1
  }
  PIN_COMMIT_TIME=$(git log -1 --format=%cI "$PIN_SHA" 2>/dev/null) || {
    echo "pin: commit $PIN_SHA not found in the executing checkout's object database" >&2
    return 1
  }
  PIN_EXEC_HEAD=$(git rev-parse HEAD 2>/dev/null || true)
}

# Is the mounted custom_components byte-identical to the tree of PIN_SHA? Content proof instead of `git status`, so no git
# command has to run inside the mount-source checkout. Prints differences; returns non-zero on any.
mount_clean() {
  local bad=0 meta path blob f tracked ondisk
  tracked=$(mktemp)
  ondisk=$(mktemp)
  while IFS=$'\t' read -r meta path; do
    blob=$(awk '{print $3}' <<<"$meta")
    echo "$path" >>"$tracked"
    f="$PIN_ROOT/$path"
    if [ ! -f "$f" ]; then
      echo "missing on disk: $path"
      bad=1
    elif [ "$(git hash-object --no-filters "$f")" != "$blob" ]; then
      echo "differs from $PIN_SHA: $path"
      bad=1
    fi
  done < <(git ls-tree -r "$PIN_SHA" -- custom_components)
  (cd "$PIN_ROOT" && find custom_components -type f -not -path '*/__pycache__/*') | sort >"$ondisk"
  sort -o "$tracked" "$tracked"
  if ! diff -q "$tracked" "$ondisk" >/dev/null; then
    echo "file list differs from the tree of $PIN_SHA:"
    diff "$tracked" "$ondisk" | grep '^[<>]' | sed 's/^/  /'
    bad=1
  fi
  rm -f "$tracked" "$ondisk"
  return $bad
}

# sha256 of a component file on the host (mount source) and inside a container: prints "host container"
mount_hashes() {
  local letter=$1 file=$2 c h k
  c=$(inst_container "$letter") || return 1
  h=$(sha256sum "$(mount_src)/$file" | cut -d' ' -f1)
  k=$(podman exec "$c" sha256sum "/config/custom_components/mqtt_actions/$file" 2>/dev/null | cut -d' ' -f1)
  echo "$h $k"
}

# ---- http ----------------------------------------------------------------------------------------------------------
# Poll /api/ until it answers 401 or 200 (HA is up), at most 240 s.
wait_http() {
  local port=$1 i code
  for ((i = 0; i < 120; i++)); do
    code=$(curl -s -o /dev/null -m 3 -w '%{http_code}' "http://localhost:$port/api/" || true)
    case "$code" in 401 | 200) return 0 ;; esac
    sleep 2
  done
  echo "wait_http: port $port did not answer within 240 s" >&2
  return 1
}

# ---- broker probe ---------------------------------------------------------------------------------------------------
# Passwords come from the 0600 env file via a temporary options file (never on the command line, never echoed).
_env_get() { sed -n "s/^$1=//p" "$ENVF" 2>/dev/null | head -n1; }
_with_opts() { # _with_opts USER PWVAR cmd args... ; the options file is removed afterwards
  local user=$1 pwvar=$2 of rc
  shift 2
  of=$(mktemp)
  chmod 600 "$of"
  printf -- '-u %s\n-P %s\n' "$user" "$(_env_get "$pwvar")" >"$of"
  "$@" -o "$of"
  rc=$?
  rm -f "$of"
  return $rc
}
# probe_sub|probe_pub|bridge_sub|bridge_pub ARGS...  (host and port are fixed to the bench broker)
probe_sub() { _with_opts uat_probe UAT_PROBE_PW mosquitto_sub -h localhost -p 1883 "$@"; }
probe_pub() { _with_opts uat_probe UAT_PROBE_PW mosquitto_pub -h localhost -p 1883 "$@"; }
bridge_sub() { _with_opts uat_bridge UAT_BRIDGE_PW mosquitto_sub -h localhost -p 1883 "$@"; }
bridge_pub() { _with_opts uat_bridge UAT_BRIDGE_PW mosquitto_pub -h localhost -p 1883 "$@"; }

# ---- registry rows --------------------------------------------------------------------------------------------------
# Rows of a COPY of a core.entity_registry file. Only the integration's own platforms are listed with their ids; any other
# entity is listed (platform, entity_id) only when its id ends in _2, so a duplicate anywhere is still visible without
# publishing unrelated device identifiers.
reg_rows() {
  local src=$1 tmp
  tmp=$(mktemp)
  cp "$src" "$tmp"
  jq -S '[.data.entities[]
          | if (.platform == "mqtt" or .platform == "mqtt_actions")
            then {platform, entity_id, id, unique_id, device_id, disabled_by}
            elif (.entity_id | test("_2$")) then {platform, entity_id}
            else empty end]
         | sort_by(.entity_id, .unique_id)' "$tmp"
  rm -f "$tmp"
}

# ---- verdicts -------------------------------------------------------------------------------------------------------
# verdict DIR PASS|FAIL|ABORT [reason lines...] : first token of verdict.txt is the result. ABORT = bench problem, never a
# UAT result.
verdict() {
  local dir=$1 res=$2
  shift 2
  mkdir -p "$dir"
  {
    echo "$res"
    for l in "$@"; do echo "$l"; done
  } >"$dir/verdict.txt"
}

# Plain output helpers for check scripts: collect failures, print one result line at the end.
CHK_FAILS=()
chk_fail() { CHK_FAILS+=("$1"); }
chk_finish() { # chk_finish NAME EVIDENCE_PATH ; exit code 0 PASS, 1 FAIL
  if [ "${#CHK_FAILS[@]}" -eq 0 ]; then
    echo "PASS $1 $2"
    return 0
  fi
  echo "FAIL $1"
  printf '  - %s\n' "${CHK_FAILS[@]}"
  return 1
}
