#!/usr/bin/env bash
# CI gate — the two static budgets (PM Decisions 001 §1).
#
#   RAM    200 KiB   .data + .bss + the engine instance
#   Flash   32 KiB   .rodata
#
# Both are asserted, and both print on every run whether they pass or not, so
# growth is visible long before it is a problem.
#
# The RAM budget includes the engine instance returned by tape_instance_size()
# (spec/engine-api.md §4). The instance lives in caller-supplied memory, so it
# is invisible to `size` -- it is measured by linking a one-line program against
# the archive and asking. Without that the budget would look almost empty while
# the real consumer, two 48 KiB index arrays, went uncounted.
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

# Ask the engine how big its instance is. Any failure here is a broken gate, not
# a pass: a budget that silently omits its dominant term is worse than none.
probe=build/engine/_instance_size
mkdir -p build/engine
cat > "$probe.c" <<'PROBE'
#include <stdio.h>
#include "tape.h"
int main(void) { printf("%zu\n", tape_instance_size()); return 0; }
PROBE
if ! ${CC:-cc} -std=c99 -Iengine/include "$probe.c" "$LIB" -o "$probe" 2>"$probe.log"; then
  echo "FAIL  gate is broken: cannot link tape_instance_size() probe"
  sed 's/^/        /' "$probe.log" | head -10
  exit 2
fi
instance=$("$probe") || { echo "FAIL  gate is broken: probe did not run"; exit 2; }

ram=$((data + bss + instance))
rc=0

printf '        .text    %8d\n' "$text"
printf '        .data    %8d\n' "$data"
printf '        .bss     %8d\n' "$bss"
printf '        instance %8d   (tape_instance_size)\n' "$instance"
printf '        %-8s %8d / %d bytes  (%d%%)   RAM\n' \
       "RAM" "$ram" "$RAM_BUDGET" $(( ram * 100 / RAM_BUDGET ))
printf '        %-8s %8d / %d bytes  (%d%%)   flash\n' \
       ".rodata" "$rodata" "$ROD_BUDGET" $(( rodata * 100 / ROD_BUDGET ))

if [ "$ram" -gt "$RAM_BUDGET" ]; then
  echo "FAIL  RAM $ram exceeds 200 KiB by $((ram - RAM_BUDGET)) bytes"
  echo "      = .data $data + .bss $bss + instance $instance"
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
