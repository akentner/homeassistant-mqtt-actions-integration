#!/usr/bin/env bash
# Final gate of Phase 8 (plan 08-10): the ledger is complete, nothing recorded is stale, the evidence tree and the script copy
# hold no secret, and the archived Phase 1 to 4 reports read the status the ledger allows (D-05, D-06, D-07; T-08-28, T-08-29,
# T-08-30).
#   check-final.sh                 full: every assertion, including the per-phase report status of Phases 1 to 4
#   check-final.sh --pre           before the verifier runs (Task 2): the status of Phases 1 to 3 is printed but not asserted
#                                  (they still read human_needed then); Phase 4 passed is asserted
#   check-final.sh --commit-shape  after the report commit (plan 08-15 Task 3): the last commit holds at most seven files (the four
#                                  archived reports, 08-VERIFICATION.md, ROADMAP.md, 08-VALIDATION.md; never the ledger), no file under
#                                  .planning/phases/ belongs to Phases 1 to 5, and the working tree is clean apart from the owner's own
#                                  unrelated ` M .planning/config.json` modification
# Status expectation (full mode): a phase reads `passed` when every one of its items (ledger blocks of the item-to-report mapping
# below) is `pass` or carries an `override_by:` line; it reads something other than `passed` (human_needed or gaps_found) when an
# item is an unresolved issue (T-08-28). Phase 4 has no human item and must read `passed`.
# Gaps rule: every `issue` block has a Gaps entry with its block number, and every Gaps entry points at an `issue` block; the allowed
# exceptions are a follow-up entry that says so with `status: follow-up` and (plan 08-15) a `status: resolved` entry whose block is
# `pass` and that carries a `resolution:` line (a resolved entry on a block that is not pass, or without a resolution line, fails).
# Phase 8 report (full mode, plan 08-15): `verification status` of the Phase 8 directory reads `passed` exactly when no ledger block is
# an issue and every Gaps entry is resolved, and something else otherwise.
# Run from inside the checkout that holds the ledger. Prints one line per assertion (ok or FAIL) and a final PASS or FAIL.
# Exit 0 PASS, 1 FAIL, 2 usage or bench problem (ABORT).
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"

GSD_TOOLS="$HOME/.claude/gsd-core/bin/gsd-tools.cjs"
ARCHIVE=".planning/milestones/v1.0-phases"
declare -A PDIR=(
  [1]="01-walking-skeleton-installable-switch"
  [2]="02-select-devices-and-reliable-execution"
  [3]="03-trust-central-config-and-ownership"
  [4]="04-operations-recovery-and-release"
)
# item-to-report mapping of plan 08-10: the ledger blocks that are a phase's human items
declare -A PBLOCKS=([1]="5 6 7 8 9 10" [2]="11 12" [3]="13 14" [4]="")
IDS=(UAT-01 UAT-02 UAT-03 UAT-04 P1-1 P1-2 P1-3 P1-4 P1-5 P1-6 P2-1 P2-2 P3-1 P3-2)
REQS=(UAT-01 UAT-02 UAT-03 UAT-04)

mode=${1:-}
case "$mode" in "" | --pre | --commit-shape) ;; *)
  echo "usage: check-final.sh [--pre | --commit-shape]" >&2
  exit 2
  ;;
esac

top=$(git rev-parse --show-toplevel 2>/dev/null) || {
  echo "ABORT run from inside the checkout that holds the ledger"
  exit 2
}
cd "$top" || exit 2
UAT="$PHASE_DIR_REL/08-UAT.md"
EV="$PHASE_DIR_REL/08-evidence"
[ -f "$UAT" ] || {
  echo "ABORT $UAT does not exist"
  exit 2
}
# the first pin of the phase (build.txt first_sha after a re-pin, the sha itself before one)
FIRST_SHA=$(sed -n 's/^first_sha: //p' "$EV/00-preflight/build.txt" 2>/dev/null | head -n1)
[ -n "$FIRST_SHA" ] || FIRST_SHA=$(sed -n 's/^sha: //p' "$EV/00-preflight/build.txt" 2>/dev/null | head -n1)

fails=0
ok() { echo "ok   $1"; }
bad() {
  echo "FAIL $1"
  fails=$((fails + 1))
}
assert() { # assert RC TEXT
  if [ "$1" -eq 0 ]; then ok "$2"; else bad "$2"; fi
}
finish() {
  if [ "$fails" -eq 0 ]; then
    echo "PASS final gate${mode:+ ($mode)} $UAT"
    exit 0
  fi
  echo "FAIL final gate${mode:+ ($mode)}: $fails assertion(s) failed"
  exit 1
}

# ---- ledger parsing (same shapes as check-recorded.sh) --------------------------------------------------------------
section() { awk -v h="$1" '/^## /{on = ($0 == "## " h)} on' "$UAT"; }
block_n() { # the lines of block number N
  awk -v n="$1" '/^##/ { on = ($0 ~ ("^### " n "\\. ")) } on' "$UAT"
}
block_id() { awk -v id="$1" '/^##/ { on = ($0 ~ ("^### [0-9]+\\. " id ": ")) } on' "$UAT"; }
field() { sed -n "s/^$2:[[:space:]]*//p" <<<"$1" | head -n1; }
front() { awk 'NR==1 && $0!="---"{exit} NR>1 && $0=="---"{exit} NR>1' "$UAT" | sed -n "s/^$1:[[:space:]]*//p" | head -n1; }
# verdict_row REQ: the Verdict cell of the Requirement verdicts table
verdict_row() {
  awk -F'|' -v id="$1" '
    /^## Requirement verdicts/ { on = 1; next }
    /^## / { on = 0 }
    on && $2 ~ ("^[[:space:]]*" id "[[:space:]]*$") { gsub(/^[ \t]+|[ \t]+$/, "", $4); print $4; exit }' "$UAT"
}
# gap_entries: one "test status resolution" triple per Gaps entry (an entry starts at "- truth:"); status is "-" when the entry has
# none, resolution is "res" when the entry carries a non-empty `resolution:` line and "nores" otherwise
gap_entries() {
  section Gaps | awk '
    function flush() { if (t != "") print t, (s == "" ? "-" : s), (r ? "res" : "nores") }
    /^- / { flush(); t = ""; s = ""; r = 0 }
    /^[[:space:]]*test:/ { sub(/^[[:space:]]*test:[[:space:]]*/, ""); t = $0 }
    /^[[:space:]]*status:/ { sub(/^[[:space:]]*status:[[:space:]]*/, ""); s = $0 }
    /^[[:space:]]*resolution:[[:space:]]*[^[:space:]]/ { r = 1 }
    END { flush() }'
}

# ======================================================================================================================
if [ "$mode" = "--commit-shape" ]; then
  allowed=(
    "$ARCHIVE/${PDIR[1]}/01-VERIFICATION.md"
    "$ARCHIVE/${PDIR[2]}/02-VERIFICATION.md"
    "$ARCHIVE/${PDIR[3]}/03-VERIFICATION.md"
    "$ARCHIVE/${PDIR[4]}/04-VERIFICATION.md"
    "$PHASE_DIR_REL/08-VERIFICATION.md"
    "$PHASE_DIR_REL/08-VALIDATION.md"
    ".planning/ROADMAP.md"
  )
  files=$(git show --first-parent --name-only --format= HEAD 2>&1)
  rc=$?
  assert "$rc" "last commit readable ($(git rev-parse --short HEAD 2>/dev/null))"
  if [ "$rc" -eq 0 ]; then
    n=$(grep -c . <<<"$files")
    if [ "$n" -le 7 ] && [ "$n" -ge 1 ]; then
      ok "last commit holds $n file(s), at most seven"
    else
      bad "last commit holds $n file(s), expected 1 to 7"
    fi
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      hit=0
      for a in "${allowed[@]}"; do [ "$f" = "$a" ] && hit=1; done
      assert $((1 - hit)) "last commit file is a report, ROADMAP.md or the validation map: $f"
    done <<<"$files"
  fi
  tracked=$(git ls-files -- .planning/phases 2>&1)
  rc=$?
  assert "$rc" "tracked files under .planning/phases readable"
  if [ "$rc" -eq 0 ]; then
    revived=$(grep -E '^\.planning/phases/0[1-5]-' <<<"$tracked" || true)
    assert "$([ -z "$revived" ] && echo 0 || echo 1)" "no tracked file under .planning/phases/ belongs to Phases 1 to 5${revived:+: $(tr '\n' ' ' <<<"$revived")}"
  fi
  ondisk=$(find .planning/phases -mindepth 1 -maxdepth 1 -name '0[1-5]-*' 2>/dev/null)
  assert "$([ -z "$ondisk" ] && echo 0 || echo 1)" "no directory for Phases 1 to 5 under .planning/phases/${ondisk:+: $(tr '\n' ' ' <<<"$ondisk")}"
  st=$(git status --porcelain 2>&1)
  rc=$?
  assert "$rc" "working tree status readable"
  # the owner's own unrelated ` M .planning/config.json` modification is tolerated (never staged or committed by a plan)
  [ "$rc" -eq 0 ] && st=$(grep -v '^ M \.planning/config\.json$' <<<"$st" || true)
  [ "$rc" -eq 0 ] && assert "$([ -z "$st" ] && echo 0 || echo 1)" "working tree clean (apart from .planning/config.json)${st:+: $(tr '\n' ' ' <<<"$st")}"
  finish
fi

# ======================================================================================================================
# 1. the ledger as a whole
out=$("$here/check-recorded.sh" --all 2>&1)
assert $? "check-recorded.sh --all: ${out%%$'\n'*}"

section "Current Test" | grep -qi "testing complete"
assert $? "Current Test says testing complete"

issues=0
pending=0
for id in "${IDS[@]}"; do
  case "$(field "$(block_id "$id")" result)" in
    issue) issues=$((issues + 1)) ;;
    pass) ;;
    *) pending=$((pending + 1)) ;;
  esac
done
assert "$([ "$pending" -eq 0 ] && echo 0 || echo 1)" "every block is pass or issue ($pending other)"
want=complete
[ "$issues" -gt 0 ] && want=partial
st=$(front status)
assert "$([ "$st" = "$want" ] && echo 0 || echo 1)" "frontmatter status is '$st' (expected $want with $issues issue(s))"
upd=$(front updated)
rc=0
[[ "$upd" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || rc=1
assert "$rc" "frontmatter updated is a timestamp ($upd)"

# 2. gaps both ways
for id in "${IDS[@]}"; do
  b=$(block_id "$id")
  [ "$(field "$b" result)" = issue ] || continue
  n=$(sed -n 's/^### \([0-9][0-9]*\)\. .*/\1/p' <<<"$b" | head -n1)
  gap_entries | awk -v n="$n" '$1 == n { f = 1 } END { exit !f }'
  assert $? "issue block $n ($id) has a Gaps entry with test: $n"
done
while read -r t s r; do
  [ -n "$t" ] || continue
  if [ "$s" = "follow-up" ]; then
    ok "Gaps entry test: $t is a follow-up entry (allowed exception)"
    continue
  fi
  if [ "$s" = "resolved" ]; then
    rc=0
    { [[ "$t" =~ ^[0-9]+$ ]] && [ "$(field "$(block_n "$t")" result)" = pass ] && [ "$r" = res ]; } || rc=1
    assert "$rc" "Gaps entry test: $t is resolved, its block is pass and it carries a resolution line"
    continue
  fi
  rc=0
  { [[ "$t" =~ ^[0-9]+$ ]] && [ "$(field "$(block_n "$t")" result)" = issue ]; } || rc=1
  assert "$rc" "Gaps entry test: $t points at an issue block"
done < <(gap_entries)

# 3. requirement verdicts
section "Requirement verdicts" | grep -q .
assert $? "section Requirement verdicts exists"
for r in "${REQS[@]}"; do
  vcell=$(verdict_row "$r")
  v=${vcell%% *} # the first token is compared, so `pass (only on a pruned registry state)` equals a pass block
  res=$(field "$(block_id "$r")" result)
  case "$v" in pass | issue) ;; *) v="(missing: '$vcell')" ;; esac
  assert "$([ "$v" = "$res" ] && echo 0 || echo 1)" "verdict $r is '$v' and equals its block ('$res')"
  if [ "$r" = UAT-04 ] && [ "$res" = pass ]; then
    disp=$("$here/check-uat04-iso.sh" disposition 2>/dev/null | head -n1)
    case "$disp" in
      document | bench-artifact)
        rc=0
        grep -qF '(only on a pruned registry state)' <<<"$vcell" || rc=1
        assert "$rc" "UAT-04 verdict carries '(only on a pruned registry state)' (disposition $disp)"
        ;;
      guard | guard-and-document) ok "UAT-04 pass is on the failing state, no pruned-state qualifier needed (disposition $disp)" ;;
      *) bad "UAT-04 disposition unreadable ('$disp')" ;;
    esac
  fi
done
for s in "Bench state left behind" "Owner follow-ups"; do
  rc=0
  [ "$(section "$s" | grep -c .)" -gt 1 ] || rc=1
  assert "$rc" "section $s exists and is not empty"
done

# 4. stale anchor (D-03)
out=$("$here/check-stale-anchor.sh" 2>&1)
assert $? "check-stale-anchor.sh: $(tail -n1 <<<"$out")"
rec=$(sed -n 's/^sha: //p' "$EV/00-preflight/build.txt" | head -n1)
f="$EV/00-preflight/stale-anchor-final.txt"
[ -s "$f" ] && grep -q "^recorded build sha: $rec\$" "$f" && grep -q '^stale: no' "$f" && grep -q '^PASS stale anchor' "$f"
assert $? "stale-anchor-final.txt holds the recorded sha, 'stale: no' and the PASS line"

# 5. the script copy and the evidence tree (T-08-29)
d="$EV/00-preflight/bench-scripts"
rc=0
for f in lib.sh ha-test-guard ha-test-ws.py check-recorded.sh check-evidence-clean.sh check-stale-anchor.sh run-all-scripted.sh README.txt; do
  [ -s "$d/$f" ] || rc=1
done
assert "$rc" "bench-scripts copy holds the helper scripts and a README"
stray=$(find "$d" -type f \( -name '*.env' -o -name '.token-*' -o -name '.storage' -o -name '.ha-c-owner' -o -name '*.txt' ! -name README.txt \) 2>/dev/null)
assert "$([ -z "$stray" ] && echo 0 || echo 1)" "bench-scripts copy holds scripts only${stray:+: $(tr '\n' ' ' <<<"$stray")}"
out=$("$here/check-evidence-clean.sh" "$d" 2>&1)
assert $? "check-evidence-clean.sh over the script copy: ${out%%$'\n'*}"
out=$("$here/check-evidence-clean.sh" "$EV" 2>&1)
assert $? "check-evidence-clean.sh over the whole evidence tree: ${out%%$'\n'*}"
[ -s "$EV/00-preflight/bench-state-final.txt" ]
assert $? "bench-state-final.txt exists"

# 6. the archived reports (D-06, D-07, T-08-28)
[ -f "$GSD_TOOLS" ] || {
  echo "ABORT $GSD_TOOLS is missing"
  exit 2
}
for p in 1 2 3 4; do
  dir="$ARCHIVE/${PDIR[$p]}"
  st=$(node "$GSD_TOOLS" query verification status "$dir" --pick status 2>&1)
  rc=$?
  if [ "$rc" -ne 0 ] || [ -z "$st" ]; then
    bad "Phase $p: verification status could not be read (rc=$rc): ${st%%$'\n'*}"
    continue
  fi
  expect=passed
  open=""
  for n in ${PBLOCKS[$p]}; do
    b=$(block_n "$n")
    if [ "$(field "$b" result)" != pass ] && [ -z "$(field "$b" override_by)" ]; then
      expect="not passed"
      open="$open $n"
    fi
  done
  # Phase 4 is asserted in --pre only while the product, tests and workflow are unchanged since the first pin; when they changed
  # (a guard disposition, plan 08-15 path A) the verifier judges Phase 4 again, so it is printed, not asserted, before that run
  if [ "$mode" = "--pre" ] && { [ "$p" -ne 4 ] || ! git diff --quiet "$FIRST_SHA" HEAD -- custom_components tests .github; }; then
    echo "info Phase $p report reads '$st' (expected '$expect' once the verifier has run; not asserted in --pre)"
    continue
  fi
  if [ "$expect" = passed ]; then
    assert "$([ "$st" = passed ] && echo 0 || echo 1)" "Phase $p report reads '$st' (expected passed: items${PBLOCKS[$p]:+ blocks${PBLOCKS[$p]// / }} all pass or overridden)"
  else
    assert "$([ "$st" != passed ] && echo 0 || echo 1)" "Phase $p report reads '$st' (expected not passed: unresolved issue in block(s)$open)"
  fi
done

# 7. Phase 8's own report (plan 08-15): passed exactly when no ledger block is an issue and every Gaps entry is resolved
open_gaps=0
while read -r t st2 r; do
  [ -n "$t" ] || continue
  [ "$st2" = resolved ] || open_gaps=$((open_gaps + 1))
done < <(gap_entries)
expect8=passed
{ [ "$issues" -gt 0 ] || [ "$open_gaps" -gt 0 ]; } && expect8="not passed"
st8=$(node "$GSD_TOOLS" query verification status "$PHASE_DIR_REL" --pick status 2>&1)
rc=$?
if [ "$rc" -ne 0 ] || [ -z "$st8" ]; then
  bad "Phase 8: verification status could not be read (rc=$rc): ${st8%%$'\n'*}"
elif [ "$mode" = "--pre" ]; then
  echo "info Phase 8 report reads '$st8' (expected '$expect8' once the verifier has run; not asserted in --pre)"
elif [ "$expect8" = passed ]; then
  assert "$([ "$st8" = passed ] && echo 0 || echo 1)" "Phase 8 report reads '$st8' (expected passed: $issues issue block(s), $open_gaps unresolved Gaps entr(ies))"
else
  assert "$([ "$st8" != passed ] && echo 0 || echo 1)" "Phase 8 report reads '$st8' (expected not passed: $issues issue block(s), $open_gaps unresolved Gaps entr(ies))"
fi

finish
