#!/usr/bin/env bash
# Meta-gate — prove every guardrail gate can actually go red.
#
# From PM Decisions 004 §6, and it is the generalisation of a real defect:
#
#     A gate that measures the wrong quantity reads as green.
#
# 98 KB of static buffers sat in .bss through green run after green run. The
# allocation gate was asking "is anything malloc'd?" while the guardrail's
# actual intent was "does the engine's RAM fit, and is it all in the caller's
# instance?" Nothing was malloc'd, so it passed -- while a reentrancy bug that
# would have corrupted a cartridge sat in plain sight.
#
# The lesson is not "write better gates". It is that a gate you have never seen
# fail is a gate you have not tested. So this plants a known violation for each
# one, asserts it goes red, removes it, and asserts it goes green again.
#
# It runs in CI. If a gate ever stops being able to fail -- a broken pattern, a
# swallowed exit code, a probe the optimiser deletes -- this is what says so.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

PROBE=engine/src/_gateprobe.c
pass=0; fail=0; failed=()

cleanup() { rm -f "$PROBE"; rm -rf build/engine; make -C engine all >/dev/null 2>&1 || true; }
trap cleanup EXIT

rebuild() { rm -rf build/engine; make -C engine all >/dev/null 2>&1; }

# expect <red|green> <name> <gate command...>
expect() {
  local want=$1 name=$2; shift 2
  local out status
  out=$("$@" 2>&1); status=$?
  if { [ "$want" = red ] && [ $status -ne 0 ]; } || { [ "$want" = green ] && [ $status -eq 0 ]; }; then
    echo "  ok    $name — goes $want on demand"
    pass=$((pass+1))
  else
    echo "  BROKEN $name — expected $want, gate exited $status"
    printf '        %s\n' "$out" | head -6
    fail=$((fail+1)); failed+=("$name")
  fi
}

echo "== meta-gate: can each gate go red? =="

# --- allocation: guardrail 08 -------------------------------------------------
cat > "$PROBE" <<'EOF'
#include <stdlib.h>
void *gp_sink;
void gp(void); void gp(void) { gp_sink = malloc(16); }
EOF
rebuild
expect red "allocation" ./tools/ci/audit-allocation.sh

# --- indirect calls: guardrail 09 --------------------------------------------
cat > "$PROBE" <<'EOF'
#include "dev.h"
int gp(const tape_dev *d, void *b);
int gp(const tape_dev *d, void *b) { return d->read(d->ctx, 0u, 1u, b); }
EOF
rebuild
expect red "indirect funnel (source)" ./tools/ci/audit-indirect.sh

# A static dispatch table: the source check cannot see this one, so it proves
# the link-time backstop independently.
cat > "$PROBE" <<'EOF'
static int a(void) { return 1; }
static int b(void) { return 2; }
typedef int (*fn)(void);
const fn gp_table[2] = { a, b };
int gp(unsigned i); int gp(unsigned i) { return gp_table[i & 1u](); }
EOF
rebuild
expect red "indirect funnel (link backstop)" ./tools/ci/audit-indirect.sh

# --- stack: guardrail 08, 8 KiB ceiling --------------------------------------
cat > "$PROBE" <<'EOF'
volatile int gp_sink;
void gp_a(int n); void gp_b(int n);
void gp_a(int n) { gp_sink += n; if (n > 0) gp_b(n - 1); }
void gp_b(int n) { gp_sink ^= n; if (n > 0) gp_a(n - 1); }
EOF
rebuild
expect red "stack (recursion)" python3 tools/ci/audit-stack.py

cat > "$PROBE" <<'EOF'
volatile int gp_sink;
int gp3(int n); int gp2(int n); int gp1(int n);
int gp3(int n){ volatile char x[4000]; x[0]=(char)n; return x[0]; }
int gp2(int n){ volatile char x[4000]; x[0]=(char)gp3(n); return x[0]; }
int gp1(int n){ volatile char x[4000]; x[0]=(char)gp2(n); return x[0]; }
EOF
rebuild
expect red "stack (depth > 8 KiB)" python3 tools/ci/audit-stack.py

# --- memory: both budgets ----------------------------------------------------
# .bss, which is the exact shape of the defect that motivated this meta-gate.
cat > "$PROBE" <<'EOF'
char gp_big[300000];
void gp(void); void gp(void) { gp_big[0] = 1; }
EOF
rebuild
expect red "memory (RAM budget)" ./tools/ci/audit-memory.sh

cat > "$PROBE" <<'EOF'
#include <stdint.h>
const uint32_t gp_tbl[10000] = { 1, 2, 3 };
uint32_t gp(unsigned i); uint32_t gp(unsigned i) { return gp_tbl[i % 10000u]; }
EOF
rebuild
expect red "memory (flash budget)" ./tools/ci/audit-memory.sh

# --- and green again, with the probe gone ------------------------------------
rm -f "$PROBE"
rebuild
expect green "allocation"                    ./tools/ci/audit-allocation.sh
expect green "indirect funnel"               ./tools/ci/audit-indirect.sh
expect green "stack"                         python3 tools/ci/audit-stack.py
expect green "memory"                        ./tools/ci/audit-memory.sh

echo
echo "======================================"
if [ $fail -eq 0 ]; then
  echo "PASS  $pass/$pass — every gate demonstrably goes red on a real violation"
  exit 0
fi
echo "FAIL  $fail of $((pass + fail)) checks: a gate cannot fail, which means it is not a gate"
printf '        %s\n' "${failed[@]}"
exit 1
