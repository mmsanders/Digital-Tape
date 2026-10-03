#!/usr/bin/env bash
# WP-11 portability gate (acceptance WP-11, #366). One configuration per call:
#
#   host-gcc    (a) the host GCC, run natively
#   arm-m3      (b) the embedded target toolchain: arm-none-eabi-gcc, Cortex-M3
#                   Thumb, newlib + semihosting (rdimon), run under qemu-arm
#   narrow-int  (c) the static-assert alternative (tools/ci/wp11-narrow-int-check.py:
#                   INT_MAX/int64_t static assertions plus an AST proof that §8's
#                   subtraction casts both operands first), then the harness on host
#
# Each configuration builds the engine archive and engine/test/tape_test_hooks.c
# with its own toolchain, links the WP-11 differential harness ahead of the
# archive, and runs it. The harness is Verification's (#143) and arrives in
# Stage 2. Until then this FAILS on purpose: a green placeholder would claim a
# portability result nobody has measured.
#
# Usage: tools/ci/wp11-portability.sh host-gcc|arm-m3|narrow-int
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

CONFIG=${1:-}
# Stage 2 sets HARNESS to the imported harness sources (space-separated, from
# the repository root) and RUN_ARGS to its arguments.
HARNESS=${WP11_HARNESS:-}
RUN_ARGS=${WP11_HARNESS_ARGS:-}
OUT=build/wp11-portability/$CONFIG
ENGINE_FLAGS="-std=c99 -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion -Wstrict-prototypes \
-Wmissing-prototypes -Wvla -Wcast-qual -Wpointer-arith -Wwrite-strings -fno-common -Os"

case "$CONFIG" in
  host-gcc|narrow-int)
    CC=gcc; AR=ar; TFLAGS=""; LDFLAGS=""; RUN=""
    ;;
  arm-m3)
    CC=arm-none-eabi-gcc; AR=arm-none-eabi-ar
    TFLAGS="-mcpu=cortex-m3 -mthumb"; LDFLAGS="--specs=rdimon.specs"; RUN="qemu-arm -cpu cortex-m3"
    ;;
  *) echo "usage: $0 host-gcc|arm-m3|narrow-int"; exit 2 ;;
esac

echo "== WP-11 portability: $CONFIG =="
command -v "$CC" >/dev/null || { echo "FAIL  $CC not installed"; exit 1; }
"$CC" --version | head -1

if [ "$CONFIG" = narrow-int ]; then
  python3 -B tools/ci/wp11-narrow-int-check.py || exit 1
  python3 -B tools/ci/wp11-narrow-int-check.py --control || exit 1
fi

rm -rf "$OUT"; mkdir -p "$OUT"
# The unchanged engine, built by its own Makefile with this toolchain.
make -s -C engine all CC="$CC" AR="$AR" BUILD="../$OUT/engine" CFLAGS="$TFLAGS" >"$OUT/engine-build.log" 2>&1 \
  || { echo "FAIL  engine build with $CC"; tail -20 "$OUT/engine-build.log"; exit 1; }
echo "  ok    engine archive built with $CC"
# shellcheck disable=SC2086
"$CC" $ENGINE_FLAGS $TFLAGS -Iengine/include -Iengine/src -Iengine/test \
  -c engine/test/tape_test_hooks.c -o "$OUT/tape_test_hooks.o" \
  || { echo "FAIL  tape_test_hooks.c does not compile with $CC"; exit 1; }
echo "  ok    tape_test_hooks.o built with $CC"

if [ -z "$HARNESS" ]; then
  echo "FAIL  WP-11 differential harness not imported yet (Verification #143, #366 Stage 2)."
  echo "      This gate stays red until the harness runs green on this configuration."
  exit 1
fi

# shellcheck disable=SC2086
"$CC" $ENGINE_FLAGS $TFLAGS $LDFLAGS -Iengine/include -Iengine/test $HARNESS \
  "$OUT/tape_test_hooks.o" "$OUT/engine/libtape.a" -o "$OUT/wp11_differential" \
  || { echo "FAIL  harness does not build with $CC"; exit 1; }
echo "  ok    harness linked (hook ahead of libtape.a)"
# shellcheck disable=SC2086
$RUN "$OUT/wp11_differential" $RUN_ARGS
rc=$?
if [ $rc -ne 0 ]; then echo "FAIL  WP-11 differential on $CONFIG exited $rc"; exit 1; fi
echo "PASS  WP-11 differential on $CONFIG"
