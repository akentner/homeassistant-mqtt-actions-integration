#!/usr/bin/env bash
# Scan an evidence tree (default: the whole 08-evidence tree) for secrets before anything is committed (T-08-02).
#   check-evidence-clean.sh [dir]     prints PASS or FAIL; a finding shows file:line and the rule, never the matched value
set -uo pipefail
HT="$HOME/ha-test"
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=lib.sh
. "$here/lib.sh"

dir=${1:-$(evidence_root)}
[ -d "$dir" ] || {
  echo "FAIL evidence directory $dir does not exist"
  exit 1
}

findings=()

# 1. exact values of every secret the bench knows (token files, values of the env file); short values are skipped because
#    they would match everything
secrets=$(mktemp)
chmod 600 "$secrets"
for f in "$HT"/.token-*; do
  [ -f "$f" ] && tr -d '\r\n' <"$f" && echo
done >>"$secrets"
[ -f "$ENVF" ] && sed -n 's/^[A-Za-z_][A-Za-z0-9_]*=//p' "$ENVF" >>"$secrets"
awk 'length($0) >= 8' "$secrets" >"$secrets.f"
mv "$secrets.f" "$secrets"
if [ -s "$secrets" ]; then
  while IFS= read -r hit; do
    findings+=("secret value: $hit")
  done < <(grep -rnIF -f "$secrets" "$dir" 2>/dev/null | cut -d: -f1,2)
fi
rm -f "$secrets"

# 2. patterns: JSON Web Token, long Bearer value, forbidden JSON keys
scan() { # scan LABEL ERE
  local label=$1 re=$2 hit
  while IFS= read -r hit; do
    findings+=("$label: $hit")
  done < <(grep -rnIE "$re" "$dir" 2>/dev/null | cut -d: -f1,2)
}
scan "JSON Web Token" 'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.'
scan "Bearer header" 'Bearer[ ]+[A-Za-z0-9._~+/=-]{20,}'
scan "forbidden key" '"(password|access_token|refresh_token|client_secret)"[[:space:]]*:'

# 3. forbidden file names
while IFS= read -r hit; do
  findings+=("forbidden file name: $hit")
done < <(find "$dir" -type f \( -name auth -o -name 'core.config_entries' -o -name '*.db' \) 2>/dev/null)

if [ "${#findings[@]}" -eq 0 ]; then
  echo "PASS evidence clean: $dir"
  exit 0
fi
echo "FAIL evidence not clean: $dir"
printf '  - %s\n' "${findings[@]}"
exit 1
