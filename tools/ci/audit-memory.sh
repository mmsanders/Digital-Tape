#!/usr/bin/env bash
# CI gate 4 — guardrail 08: static budget under 200 KB.
#
# NOTE FOR WP-03: this counts .data + .bss as the RAM budget and reports .rodata
# separately, on the reasoning that .rodata lives in flash on the target. The
# charter says "static budget under 200 KB" without splitting them. spec/engine-api.md
# must state which. Logged in DECISIONS.md as ADR-006 and raised as a pm-decision.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

LIB=build/engine/libtape.a
SIZE=${SIZE:-size}
BUDGET=$((200 * 1024))

echo "== gate: memory budget audit =="
if [ ! -f "$LIB" ]; then
  echo "FAIL  $LIB not built — cannot audit"
  exit 1
fi

# COMMON symbols are sized by the linker, not by `size`, so they would slip past
# this audit entirely. -fno-common in engine/Makefile prevents them; this asserts
# nobody quietly dropped the flag.
common=$(${NM:-nm} --format=posix "$LIB" 2>/dev/null | awk '$2=="C"{print $1}')
if [ -n "$common" ]; then
  echo "FAIL  COMMON symbols present — -fno-common was dropped from CFLAGS:"
  printf '        %s\n' $common
  echo "      These are invisible to this audit until link time. Restore the flag."
  exit 1
fi

read -r text data bss < <($SIZE -t --format=sysv "$LIB" 2>/dev/null \
  | awk '/^\.text/{t+=$2} /^\.data/{d+=$2} /^\.bss/{b+=$2} END{print t+0, d+0, b+0}')
rodata=$($SIZE -t --format=sysv "$LIB" 2>/dev/null | awk '/^\.rodata/{r+=$2} END{print r+0}')

ram=$((data + bss))
echo "        .text   $text"
echo "        .rodata $rodata  (flash on target, not counted against RAM)"
echo "        .data   $data"
echo "        .bss    $bss"
echo "        ------  RAM = .data + .bss = $ram / $BUDGET bytes"

if [ "$ram" -gt "$BUDGET" ]; then
  echo "FAIL  static RAM $ram exceeds 200 KB budget by $((ram - BUDGET)) bytes"
  exit 1
fi
echo "PASS  static RAM within budget"

# Known limitation, for WP-03: this measures the archive. The authoritative
# number for firmware is the linked image's map file, which also accounts for
# stack and for what the toolchain elided. Add that gate when Stream 4 links.
