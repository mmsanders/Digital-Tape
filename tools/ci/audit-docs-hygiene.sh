#!/usr/bin/env bash
# Docs hygiene gate — stop the repository growing into itself.
#
# docs/ reached 31 MB while holding a 14 MB and a 9.3 MB observation.json.
# Fifteen copies each of tapefs-v1.md and engine-api.md live in evidence trees;
# those are legitimate and stay -- they are held in place by tamper controls
# (VT8-A13, PB8-A01) and deduplicating them breaks the controls. Nothing stopped
# the next one, so this does.
#
# It enforces three things:
#   1. line budgets on the two state files (CLAUDE.md §4)
#   2. no PR adds a file over 1 MiB under docs/
#   3. a warning when docs/ grows more than 2 MiB in one PR
#
# (2) and (3) are diff-based: an existing large file is not this PR's fault, and
# the goal is to stop growth, not to relitigate history. Removing a large blob
# from HEAD does not shrink a clone anyway -- history keeps it, which is correct,
# because dispositions cite it.
#
# Usage: audit-docs-hygiene.sh [BASE_REF]
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

BASE="${1:-}"
LIMIT=$((1024 * 1024))     # 1 MiB per added docs/ file
GROWTH=$((2 * 1024 * 1024))  # 2 MiB docs/ growth warning
fail=0

echo "== docs hygiene =="

# --- 1. Line budgets (CLAUDE.md §4) ------------------------------------------
check_lines() {
  local f=$1 max=$2 n
  [ -f "$f" ] || { echo "  FAIL  $f is missing"; fail=1; return; }
  n=$(wc -l < "$f")
  if [ "$n" -gt "$max" ]; then
    echo "  FAIL  $f is $n lines, budget $max"
    echo "        Move the oldest content to docs/archive/ in this same commit,"
    echo "        with a pointer and the relocated file's recorded SHA-256."
    fail=1
  else
    echo "  ok    $f $n/$max lines"
  fi
}
check_lines docs/STATUS.md 120
check_lines docs/VERIFICATION-INTEGRATION.md 150

# --- 2/3. Diff-based checks ---------------------------------------------------
if [ -z "$BASE" ]; then
  echo "  skip  added-file size and growth checks (no base ref given)"
  echo "== docs hygiene: $([ $fail -eq 0 ] && echo PASS || echo FAIL) =="
  exit $fail
fi

if ! git rev-parse --verify --quiet "$BASE^{commit}" >/dev/null; then
  echo "  FAIL  base ref '$BASE' is not a commit in this clone"
  exit 2
fi

# Any docs/ file over the limit that is new, or that grew past the limit, in
# this PR. Read from the WORKING TREE and compared against BASE by path, so the
# check needs no commit of its own and its negative control mutates no git
# state. A file that was already over the limit at BASE is not this PR's fault.
while IFS= read -r path; do
  [ -n "$path" ] || continue
  size=$(stat -c%s "$path")
  [ "$size" -gt "$LIMIT" ] || continue
  if git cat-file -e "$BASE:$path" 2>/dev/null; then
    was=$(git cat-file -s "$BASE:$path" 2>/dev/null || echo 0)
    if [ "$was" -gt "$LIMIT" ]; then
      echo "  note  $path is $size bytes and was already over the limit at $BASE — not this PR"
      continue
    fi
    echo "  FAIL  $path grew to $size bytes in this PR (was $was, limit $LIMIT)"
  else
    echo "  FAIL  $path is $size bytes and is added by this PR (limit $LIMIT)"
  fi
  echo "        Raw evidence over 1 MiB goes to a release asset with a committed"
  echo "        .sha256 next to the run; the hash is the citation. See CLAUDE.md §4."
  fail=1
done < <(find docs -type f -size +1024k 2>/dev/null)

# Total docs/ growth, warning only.
size_at() { git ls-tree -r -l "$1" -- docs/ 2>/dev/null | awk '{s+=$4} END {print s+0}'; }
before=$(size_at "$BASE"); after=$(size_at HEAD)
delta=$((after - before))
if [ "$delta" -gt "$GROWTH" ]; then
  echo "  WARN  docs/ grows $delta bytes in this PR (over the $GROWTH warning threshold)"
  echo "        Not a failure. Check it is evidence that has to live in the tree."
else
  echo "  ok    docs/ delta $delta bytes"
fi

echo "== docs hygiene: $([ $fail -eq 0 ] && echo PASS || echo FAIL) =="
exit $fail
