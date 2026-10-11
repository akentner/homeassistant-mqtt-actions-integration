#!/usr/bin/env bash
# Stale-anchor gate (D-03): did a product, test or workflow file change after the build SHA the checks were recorded against?
#   check-stale-anchor.sh
# Reads the `sha:` line of 00-preflight/build.txt and runs `git diff --stat {sha} {head} -- custom_components tests .github`
# for the HEAD of the mount-source checkout (read from its .git files, the object database is shared) and for the HEAD of the
# checkout this script runs in. A failing git is ABORT, never a clean result. Run from inside the checkout that holds the evidence.
# Exit: 0 PASS (both diffs empty), 1 FAIL (files touched: the scripted checks are stale, re-run them with run-all-scripted.sh),
# 2 ABORT (bench problem).
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"

rec=$(sed -n 's/^sha: //p' "$(evidence_root)/00-preflight/build.txt" 2>/dev/null | head -n1)
[[ "$rec" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ABORT no 40-hex sha in 00-preflight/build.txt"
  exit 2
}
pin || {
  echo "ABORT cannot resolve the HEAD of the mount-source checkout"
  exit 2
}
heads=("mount-source:$PIN_SHA")
[ -n "${PIN_EXEC_HEAD:-}" ] && [ "$PIN_EXEC_HEAD" != "$PIN_SHA" ] && heads+=("this-checkout:$PIN_EXEC_HEAD")

echo "recorded build sha: $rec"
stale=0
for h in "${heads[@]}"; do
  label=${h%%:*}
  target=${h#*:}
  out=$(git diff --stat "$rec" "$target" -- custom_components tests .github 2>&1)
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "ABORT git diff failed for $label ($target): $out"
    exit 2
  fi
  if [ -n "$out" ]; then
    echo "STALE $label ($target) differs from the recorded sha:"
    echo "$out"
    stale=1
  else
    echo "empty $label ($target): git diff --stat $rec $target -- custom_components tests .github"
  fi
done
if [ "$stale" -eq 0 ]; then
  echo "PASS stale anchor: custom_components, tests and .github unchanged since the recorded build sha"
  exit 0
fi
echo "FAIL stale anchor: re-run the affected checks with run-all-scripted.sh (D-03)"
exit 1
