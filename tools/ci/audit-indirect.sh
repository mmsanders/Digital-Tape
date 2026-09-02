#!/usr/bin/env bash
# CI gate — guardrail 09, made decidable by construction.
#
# The invariant is "every indirect call in the engine targets a tape_dev
# callback". That is not decidable by pattern-matching disassembly: an optimiser
# turns callbacks into jumps and switch statements into things that look like
# them. The previous gate counted indirect call sites and was wrong in both
# directions (issues #11, #12).
#
# So the invariant is enforced at the source instead. Every indirect call goes
# through one of three static inline wrappers in engine/src/dev.h, and this gate
# asserts nothing else in the engine dereferences a tape_dev member. It fails
# with a filename and a line number.
#
# Scope is the engine only. engine/port/ implements the callbacks and is outside
# the engine proper by design — see engine/Makefile.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

FUNNEL=engine/src/dev.h
LIB=build/engine/libtape.a
NM=${NM:-nm}
rc=0

# A gate that cannot run must fail, not pass. grep exits 0 for a match, 1 for no
# match, and >=2 for an error -- and an error looks exactly like "clean" if you
# write `|| true`. It bit this gate once already: the pattern begins with "-",
# grep read it as an option, exited 2, and the gate reported PASS while the
# engine called a callback directly. Hence -e, and hence this wrapper.
scan() {
  local out status
  out=$(grep -rn --include='*.c' --include='*.h' -E -e "$1" engine/src engine/include 2>&1)
  status=$?
  if [ $status -ge 2 ]; then
    echo "FAIL  gate is broken: grep exited $status scanning for '$1'"
    printf '        %s\n' "$out"
    exit 2
  fi
  printf '%s' "$out"
}

echo "== gate: indirect-call funnel =="

if [ ! -f "$FUNNEL" ]; then
  echo "FAIL  $FUNNEL is missing — the funnel is the gate"
  exit 1
fi

# 1. Source-level: the three call forms, anywhere but the funnel.
hits=$(scan '\->(read|write|flush)[[:space:]]*\(' | { grep -v "^$FUNNEL:" || true; })
if [ -n "$hits" ]; then
  echo "FAIL  tape_dev callbacks called outside $FUNNEL:"
  printf '        %s\n' "$hits"
  echo "      Guardrail 09: two function pointers are the entire coupling."
  echo "      Route the call through dev_read/dev_write/dev_flush, or escalate."
  rc=1
fi

# 2. The device context is the callbacks' business too — reaching for it
#    elsewhere is how a fourth concept starts crossing the boundary.
ctx=$(scan '\->ctx[^A-Za-z0-9_]' | { grep -v "^$FUNNEL:" || true; })
if [ -n "$ctx" ]; then
  echo "FAIL  tape_dev.ctx dereferenced outside $FUNNEL:"
  printf '        %s\n' "$ctx"
  rc=1
fi

# 3. Link-time backstop: a function address stored in a data section is a
#    dispatch table, i.e. an indirect call the source check above cannot see.
#
#    The check is "a relocation in a data section that points into .text".
#    Matching symbol NAMES is not enough: a static function's address is emitted
#    as a section-relative relocation against .text with no symbol name at all,
#    which is exactly how a file-local dispatch table would slip through.
if [ -f "$LIB" ]; then
  reloc=$(objdump -r "$LIB" 2>/dev/null)
  if [ -z "$reloc" ]; then
    echo "FAIL  gate is broken: objdump produced no relocation records for $LIB"
    exit 2
  fi
  funcs=$($NM --defined-only --format=posix "$LIB" 2>/dev/null \
            | awk '$2=="T"||$2=="t"{print $1}' | sort -u | tr '\n' '|')
  funcs=${funcs%|}
  bad=$(printf '%s' "$reloc" | awk -v fn="^(${funcs:-\$^})$" '
    /^RELOCATION RECORDS FOR \[/ {
      sec = $0; sub(/.*\[/, "", sec); sub(/\].*/, "", sec); next
    }
    /^[0-9a-f]+[ \t]+R_/ {
      if (sec !~ /^\.(rodata|data|init_array|fini_array|ctors|dtors)/) next
      t = $3; sub(/[+-]0x[0-9a-f]+$/, "", t)
      if (t ~ /^\.text/ || t ~ fn) printf "  %-24s -> %s\n", sec, $3
    }')
  if [ -n "$bad" ]; then
    echo "FAIL  engine function addresses stored in a data section:"
    printf '%s\n' "$bad"
    echo "      A dispatch table is an indirect call the source check cannot see."
    echo "      The only sanctioned function pointers in this project live in"
    echo "      struct tape_dev, and they are supplied by the caller."
    rc=1
  fi
else
  echo "      (link-time backstop skipped — $LIB not built)"
fi

if [ $rc -eq 0 ]; then
  echo "PASS  all tape_dev access funnels through $FUNNEL"
fi
exit $rc
