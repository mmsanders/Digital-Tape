#!/usr/bin/env bash
# F6 — engine/ is byte-identical to the pinned tree (FW-1 §2, §6).
#
#   engine_pin.sh [TREE-ISH]     default HEAD
#
# Compares TREE-ISH:engine with the pin. Exit 0 equal, 1 different, 2 cannot
# read the tree (a broken check is never a pass).
#
#   engine_pin.sh --control
#
# Negative control: builds a tree that differs from HEAD only by one byte
# appended to engine/README.md (in a temporary index; the work tree and the
# real index are untouched) and requires the check to report it as different.
set -uo pipefail

PIN=d96b4245e04d74078f8938744b1394c3018516f7

check() {
  local have
  have=$(git rev-parse --verify --quiet "$1:engine") || { echo "FAIL  cannot read $1:engine"; return 2; }
  if [ "$have" = "$PIN" ]; then
    echo "PASS  engine/ tree $have equals the pin"
    return 0
  fi
  echo "FAIL  engine/ tree $have differs from the pin $PIN"
  return 1
}

if [ "${1:-}" = "--control" ]; then
  tmp=$(mktemp -d) || exit 2
  trap 'rm -rf "$tmp"' EXIT
  export GIT_INDEX_FILE="$tmp/index"
  git read-tree HEAD || exit 2
  blob=$( { git cat-file blob HEAD:engine/README.md; printf 'x'; } | git hash-object -w --stdin ) || exit 2
  git update-index --cacheinfo "100644,$blob,engine/README.md" || exit 2
  tree=$(git write-tree) || exit 2
  unset GIT_INDEX_FILE
  echo "control: tree $tree (HEAD with one byte appended to engine/README.md)"
  check "$tree"
  rc=$?
  if [ $rc -eq 1 ]; then echo "PASS  control: the check reports the altered engine"; exit 0; fi
  echo "FAIL  control: the check did not report the altered engine (rc=$rc)"
  exit 1
fi

check "${1:-HEAD}"
