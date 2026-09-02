#!/usr/bin/env bash
# CI gate — the two static budgets (PM Decisions 001 §1).
#
#   RAM    200 KiB   .data + .bss + the engine instance
#   Flash   32 KiB   .rodata
#
# Both are asserted, and both print on every run whether they pass or not, so
# growth is visible long before it is a problem.
#
# PENDING DRAFT-3: the RAM budget is specified to include the engine instance
# returned by tape_instance_size(). That call does not exist yet, so the
# instance is not yet counted and the RAM figure below is a floor, not the
# total. Wired in as soon as the spec lands.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

LIB=build/engine/libtape.a
SIZE=${SIZE:-size}
NM=${NM:-nm}
RAM_BUDGET=$((200 * 1024))
ROD_BUDGET=$((32 * 1024))

echo "== gate: memory budgets =="
if [ ! -f "$LIB" ]; then
  echo "FAIL  $LIB not built — cannot audit"
  exit 1
fi

# COMMON symbols are sized by the linker, not by `size`, so they would slip past
# this audit entirely. -fno-common in engine/Makefile prevents them; this asserts
# nobody quietly dropped the flag.
common=$($NM --format=posix "$LIB" 2>/dev/null | awk '$2=="C"{print $1}')
if [ -n "$common" ]; then
  echo "FAIL  COMMON symbols present — -fno-common was dropped from CFLAGS:"
  printf '        %s\n' $common
  exit 1
fi

read -r text data bss rodata < <($SIZE -t --format=sysv "$LIB" 2>/dev/null | awk '
  /^\.text/    {t+=$2}
  /^\.data/    {d+=$2}
  /^\.bss/     {b+=$2}
  /^\.rodata/  {r+=$2}
  END {print t+0, d+0, b+0, r+0}')

ram=$((data + bss))
rc=0

printf '        .text    %8d\n' "$text"
printf '        .data    %8d\n' "$data"
printf '        .bss     %8d\n' "$bss"
printf '        %-8s %8d / %d bytes  (%d%%)   RAM\n' \
       "RAM" "$ram" "$RAM_BUDGET" $(( ram * 100 / RAM_BUDGET ))
printf '        %-8s %8d / %d bytes  (%d%%)   flash\n' \
       ".rodata" "$rodata" "$ROD_BUDGET" $(( rodata * 100 / ROD_BUDGET ))

if [ "$ram" -gt "$RAM_BUDGET" ]; then
  echo "FAIL  RAM $ram exceeds 200 KiB by $((ram - RAM_BUDGET)) bytes"
  rc=1
fi
if [ "$rodata" -gt "$ROD_BUDGET" ]; then
  echo "FAIL  .rodata $rodata exceeds 32 KiB by $((rodata - ROD_BUDGET)) bytes"
  echo "      A generous ceiling that exists beats a precise one that doesn't."
  echo "      Approaching it is an escalation, not a reason to raise it."
  rc=1
fi

[ $rc -eq 0 ] && echo "PASS  both budgets"
exit $rc

# Known limitation, for Stream 4: this measures the archive. The authoritative
# number for firmware is the linked image's map file, which also accounts for
# stack and for what the toolchain elided. That gate gets added when Stream 4
# links.
