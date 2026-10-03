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
# with its own toolchain, links Verification #143's differential harness
# (tests/wp11_portability_r63/differential.c, imported unchanged) with the hook
# ahead of the archive, and runs it. The harness is compiled with the flags its
# own README gives. Without the harness this FAILS: a green placeholder would
# claim a portability result nobody has measured.
#
# Usage: tools/ci/wp11-portability.sh host-gcc|arm-m3|narrow-int
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

CONFIG=${1:-}
# WP11_HARNESS overrides the harness sources (space-separated, from the root).
HARNESS=${WP11_HARNESS:-tests/wp11_portability_r63/differential.c}
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
    # Ubuntu's arm-none-eabi-gcc is built --without-newlib, so its own
    # freestanding <stdint.h> shadows newlib's and newlib's <inttypes.h> then
    # omits the 64-bit PRI macros. Search the C library's headers first so the
    # pair matches. Include-path plumbing only; the path comes from the toolchain.
    NEWLIB_INC=$(echo '#include <stdio.h>' | "$CC" $TFLAGS -E -H - 2>&1 >/dev/null | awk '$2 ~ /stdio\.h$/ {print $2; exit}')
    [ -n "$NEWLIB_INC" ] && TFLAGS="$TFLAGS -isystem $(dirname "$NEWLIB_INC")"
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

for h in $HARNESS; do
  if [ ! -f "$h" ]; then
    echo "FAIL  WP-11 differential harness $h not present (Verification #143)."
    echo "      This gate stays red until the harness runs green on this configuration."
    exit 1
  fi
done

# The harness's own build line (tests/wp11_portability_r63/README.md).
HARNESS_FLAGS="-std=c99 -O2 -Wall -Wextra -Werror"
# shellcheck disable=SC2086
"$CC" $HARNESS_FLAGS $TFLAGS $LDFLAGS -Iengine/include -Iengine/test $HARNESS \
  "$OUT/tape_test_hooks.o" "$OUT/engine/libtape.a" -o "$OUT/wp11_differential" \
  || { echo "FAIL  harness does not build with $CC"; exit 1; }
echo "  ok    harness linked (hook ahead of libtape.a)"
# shellcheck disable=SC2086
$RUN "$OUT/wp11_differential" $RUN_ARGS
rc=$?
if [ $rc -ne 0 ]; then echo "FAIL  WP-11 differential on $CONFIG exited $rc"; exit 1; fi
echo "PASS  WP-11 differential on $CONFIG"
