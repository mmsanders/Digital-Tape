#!/usr/bin/env bash
# Negative control for the docs hygiene gate.
#
# CLAUDE.md §1: "Every new gate needs a real negative control: a gate that never
# goes red has not established what it detects." This plants each violation the
# hygiene gate claims to catch, asserts it goes red, removes it, and asserts it
# goes green again.
#
# It mutates NOTHING in git -- no commit, no index, no reset. It writes two
# scratch files and deletes them. An earlier revision of this script used
# `git reset --hard` to unwind a probe commit and destroyed an unrelated commit
# on the branch it was run from; that is why this one touches only the working
# tree, and why it must stay that way.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

GATE=tools/ci/audit-docs-hygiene.sh
BASE="${1:-main}"
pass=0; fail=0

BAK=$(mktemp -d)
cp docs/STATUS.md docs/VERIFICATION-INTEGRATION.md "$BAK/"
PROBE=docs/_hygiene_probe.bin

cleanup() {
  cp "$BAK/STATUS.md" docs/STATUS.md
  cp "$BAK/VERIFICATION-INTEGRATION.md" docs/VERIFICATION-INTEGRATION.md
  rm -f "$PROBE"; rm -rf "$BAK"
}
trap cleanup EXIT

expect() {
  local want=$1 name=$2 status
  "$GATE" "$BASE" >/dev/null 2>&1; status=$?
  if { [ "$want" = red ] && [ $status -ne 0 ]; } || { [ "$want" = green ] && [ $status -eq 0 ]; }; then
    echo "  ok     $name — goes $want on demand"; pass=$((pass+1))
  else
    echo "  BROKEN $name — expected $want, gate exited $status"; fail=$((fail+1))
  fi
}

echo "== docs hygiene gate can go red =="

expect green "baseline, clean tree"

# 1. STATUS.md over its 120-line budget.
yes 'overflow line' | head -200 >> docs/STATUS.md
expect red "STATUS.md over 120 lines"
cp "$BAK/STATUS.md" docs/STATUS.md
expect green "STATUS.md restored"

# 2. VERIFICATION-INTEGRATION.md over its 150-line budget.
yes 'overflow line' | head -200 >> docs/VERIFICATION-INTEGRATION.md
expect red "VERIFICATION-INTEGRATION.md over 150 lines"
cp "$BAK/VERIFICATION-INTEGRATION.md" docs/VERIFICATION-INTEGRATION.md
expect green "VERIFICATION-INTEGRATION.md restored"

# 3. A new docs/ file over 1 MiB, present only in the working tree.
head -c $((1024 * 1024 + 1)) /dev/urandom > "$PROBE"
expect red "new docs/ file over 1 MiB"
rm -f "$PROBE"
expect green "oversized file removed"

echo "  $pass passed, $fail broken"
[ $fail -eq 0 ] || exit 1
