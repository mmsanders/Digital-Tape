#!/usr/bin/env bash
# The TAPECTL_TEST facts seam must be absent from the shipped binary
# (docs/WP14-CLI-CONTRACT.md §5), nor the observation and fault controls
# (host/port/tseam.h). Every seam symbol (nm) and every configuration string
# (the environment variables and fault names) is checked.
# The same check is run on tapectl-test, which contains the seam, and must go
# red there: a check that cannot fail would prove nothing about the shipped one.
#
# Usage: test_seam.sh TAPECTL TAPECTL_TEST
set -uo pipefail
SHIPPED=$1
TEST=$2

# Prints the marks found in binary $1; exit 0 when there are none.
seam_free() {
  local found=0
  local s
  for s in tapectl_test_facts_seam tseam_begin tseam_flush tseam_fault_noop_flush tseam_fault_read tseam_fault_nonnull_binding; do
    if nm "$1" 2>/dev/null | grep -q "$s"; then echo "    symbol $s"; found=1; fi
  done
  for s in TAPECTL_TEST_FACTS TAPECTL_TEST_TRACE TAPECTL_TEST_FAULT noop-flush hidden-flush-error nonnull-binding read-error:; do
    if LC_ALL=C grep -a -q -- "$s" "$1"; then echo "    string $s"; found=1; fi
  done
  return $found
}

fails=0
nm "$TEST" >/dev/null 2>&1 || { echo "  FAIL  nm cannot read $TEST"; exit 1; }
if seam_free "$SHIPPED"; then echo "  ok    shipped $(basename "$SHIPPED") contains no test seam"
else echo "  FAIL  shipped $(basename "$SHIPPED") contains the test seam"; fails=1; fi
if seam_free "$TEST" >/dev/null; then echo "  FAIL  control: the check did not find the seam in $(basename "$TEST")"; fails=1
else echo "  ok    control: the same check finds the seam in $(basename "$TEST")"; fi
[ $fails -eq 0 ] && echo "PASS  test seam absent from the shipped binary" || { echo "FAIL  test seam check"; exit 1; }
