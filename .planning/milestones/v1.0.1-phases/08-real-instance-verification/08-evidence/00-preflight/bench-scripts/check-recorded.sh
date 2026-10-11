#!/usr/bin/env bash
# Recording gate for 08-UAT.md (Phase 8). Later plans call it after writing a block.
#   check-recorded.sh --skeleton   14 numbered blocks with the known ids, each with expected: and result: pending, the D-05 table
#                                  has 14 rows, the Gaps section and the other sections exist, only the four allowed tokens
#   check-recorded.sh ID           one check (UAT-01..04, P1-1..6, P2-1, P2-2, P3-1, P3-2) is recorded correctly
#   check-recorded.sh --all        all 14 are recorded and the Summary counts equal the blocks
# Run from inside the checkout that holds 08-UAT.md. Output PASS or FAIL plus reasons. Exit 0 PASS, 1 FAIL.
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"

PHASE=$(phase_dir)
UAT="$PHASE/08-UAT.md"
IDS=(UAT-01 UAT-02 UAT-03 UAT-04 P1-1 P1-2 P1-3 P1-4 P1-5 P1-6 P2-1 P2-2 P3-1 P3-2)
SCRIPTED=" UAT-01 UAT-02 UAT-03 UAT-04 P1-5 P2-2 "

[ -f "$UAT" ] || {
  echo "FAIL $UAT does not exist"
  exit 1
}

# ---- parsing helpers ------------------------------------------------------------------------------------------------
# block ID: the lines of the block "### N. ID: name" up to the next heading
block() {
  awk -v id="$1" '
    /^##/ { on = ($0 ~ ("^### [0-9]+\\. " id ": ")) }
    on' "$UAT"
}
# field TEXT KEY: value of the first "KEY: value" line
field() { sed -n "s/^$2:[[:space:]]*//p" <<<"$1" | head -n1; }
# table_result ID: the Result cell of the D-05 row
table_result() {
  awk -F'|' -v id="$1" '
    /^## Results/ { on = 1; next }
    /^## / { on = 0 }
    on && $2 ~ ("^[[:space:]]*" id "[[:space:]]*$") { gsub(/^[ \t]+|[ \t]+$/, "", $4); print $4; exit }' "$UAT"
}
section() { awk -v h="$1" '/^## /{on = ($0 == "## " h)} on' "$UAT"; }
block_number() { sed -n 's/^### \([0-9][0-9]*\)\. .*/\1/p' <<<"$1" | head -n1; }

# ---- skeleton --------------------------------------------------------------------------------------------------------
check_skeleton() {
  local i n=0 id b hdr
  head -n1 "$UAT" | grep -q '^---$' || chk_fail "frontmatter missing"
  grep -q '^status: ' "$UAT" || chk_fail "frontmatter has no status"
  for s in "Current Test" "Build under test" "Results (D-05)" "Tests" "Summary" "Gaps" "Observations" "Owner decisions"; do
    grep -q "^## $s\$" "$UAT" || chk_fail "section '## $s' missing"
  done
  mapfile -t hdrs < <(grep -E '^### [0-9]+\. ' "$UAT")
  [ "${#hdrs[@]}" -eq 14 ] || chk_fail "expected 14 test blocks, found ${#hdrs[@]}"
  for i in "${!IDS[@]}"; do
    n=$((i + 1))
    id=${IDS[$i]}
    hdr=${hdrs[$i]:-}
    [[ "$hdr" == "### $n. $id: "* ]] || chk_fail "block $n should be '### $n. $id: ...' but is '$hdr'"
    b=$(block "$id")
    [ -n "$(field "$b" expected)" ] || chk_fail "$id has no expected: line"
    [ "$(field "$b" result)" = pending ] || chk_fail "$id is not at result: pending"
    [ -n "$(table_result "$id")" ] || chk_fail "$id has no row in the results table"
    [ "$(table_result "$id")" = pending ] || chk_fail "$id table row is not pending"
  done
  rows=$(awk -F'|' '/^## Results/{on=1;next} /^## /{on=0} on && $2 ~ /^[[:space:]]*(UAT|P[123])-[0-9]+[[:space:]]*$/' "$UAT" | wc -l)
  [ "$rows" -eq 14 ] || chk_fail "results table has $rows rows, expected 14"
  while IFS= read -r tok; do
    case "$tok" in pending | pass | issue | blocked) ;; *) chk_fail "result token '$tok' is not allowed" ;; esac
  done < <(sed -n 's/^result:[[:space:]]*//p' "$UAT")
  section "Gaps" | tail -n +2 | grep -q . || chk_fail "Gaps section is empty"
  bsha=$(sed -n 's/^sha: //p' "$(evidence_root)/00-preflight/build.txt" | head -n1)
  grep -q "^- sha: $bsha\$" "$UAT" || chk_fail "Build under test sha does not equal 00-preflight/build.txt ($bsha)"
}

# ---- one recorded check -----------------------------------------------------------------------------------------------
check_one() {
  local id=$1 b res sha date ev evdir verdict_first mism=0 tr n
  b=$(block "$id")
  [ -n "$b" ] || {
    chk_fail "$id: block not found"
    return
  }
  res=$(field "$b" result)
  case "$res" in pass | issue) ;; *)
    chk_fail "$id: result is '$res', expected pass or issue"
    return
    ;;
  esac
  sha=$(field "$b" sha)
  date=$(field "$b" date)
  ev=$(field "$b" evidence)
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || chk_fail "$id: sha is not 40 hex characters"
  [[ "$date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || chk_fail "$id: date is not an ISO date"
  [ -n "$(field "$b" note)" ] || chk_fail "$id: note is missing"
  if [ -z "$ev" ]; then
    chk_fail "$id: evidence is missing"
  else
    evdir="$(evidence_root)/${ev#*08-evidence/}"
    if [ ! -d "$evdir" ]; then
      chk_fail "$id: evidence folder $ev does not exist"
    else
      [ -n "$(find "$evdir" -type f -size +0 2>/dev/null | head -n1)" ] || chk_fail "$id: evidence folder holds no non-empty file"
      cl=$("$here/check-evidence-clean.sh" "$evdir" 2>&1) || chk_fail "$id: evidence scan: $(tr '\n' ' ' <<<"$cl")"
      verdict_first=""
      [ -f "$evdir/verdict.txt" ] && verdict_first=$(head -n1 "$evdir/verdict.txt" | awk '{print $1}')
      [ "$verdict_first" = ABORT ] && chk_fail "$id: verdict is ABORT, a bench problem is never recordable"
      if [[ "$SCRIPTED" == *" $id "* ]]; then
        [ -n "$verdict_first" ] || chk_fail "$id: scripted check without verdict.txt"
        if [ "$res" = pass ] && [ "$verdict_first" != PASS ]; then mism=1; fi
        if [ "$res" = issue ] && [ "$verdict_first" != FAIL ]; then mism=1; fi
        if [ "$mism" -eq 1 ] && [ "$verdict_first" != ABORT ]; then
          if [ "$res" = issue ] && [ "$verdict_first" = PASS ] && [ -n "$(field "$b" owner_rejected)" ]; then
            :
          elif [ -n "$(field "$b" override_by)" ]; then
            :
          else
            chk_fail "$id: recorded $res but verdict is '$verdict_first' and there is no owner_rejected: or override_by: line"
          fi
        fi
      fi
    fi
  fi
  if [ "$res" = issue ]; then
    [ -n "$(field "$b" reported)" ] || chk_fail "$id: issue without reported:"
    [ -n "$(field "$b" severity)" ] || chk_fail "$id: issue without severity:"
    n=$(block_number "$b")
    section "Gaps" | grep -qE "^[[:space:]]*test:[[:space:]]*${n}[[:space:]]*\$" || chk_fail "$id: issue without a Gaps entry with test: $n"
  fi
  tr=$(table_result "$id")
  [ "$tr" = "$res" ] || chk_fail "$id: results table shows '$tr' but the block says '$res'"
}

# ---- modes -----------------------------------------------------------------------------------------------------------
mode=${1:-}
case "$mode" in
  --skeleton)
    check_skeleton
    chk_finish "08-UAT.md skeleton" "$UAT"
    ;;
  --all)
    for id in "${IDS[@]}"; do check_one "$id"; done
    t=0 p=0 i=0 pe=0 bl=0
    for id in "${IDS[@]}"; do
      t=$((t + 1))
      case "$(field "$(block "$id")" result)" in pass) p=$((p + 1)) ;; issue) i=$((i + 1)) ;; pending) pe=$((pe + 1)) ;; blocked) bl=$((bl + 1)) ;; esac
    done
    s=$(section Summary)
    for pair in "total:$t" "passed:$p" "issues:$i" "pending:$pe" "blocked:$bl" "skipped:0"; do
      k=${pair%%:*}
      v=${pair##*:}
      [ "$(field "$s" "$k")" = "$v" ] || chk_fail "Summary $k is '$(field "$s" "$k")' but the blocks say $v"
    done
    chk_finish "all 14 checks recorded" "$UAT"
    ;;
  UAT-0[1-4] | P1-[1-6] | P2-[12] | P3-[12])
    check_one "$mode"
    chk_finish "$mode recorded" "$UAT"
    ;;
  *)
    echo "usage: check-recorded.sh --skeleton | --all | {UAT-01..04|P1-1..6|P2-1|P2-2|P3-1|P3-2}" >&2
    exit 2
    ;;
esac
