#!/usr/bin/env bash
# The TAPECTL_TEST facts seam must be absent from the shipped binary
# (docs/WP14-CLI-CONTRACT.md §5). Two independent marks are checked:
#   the symbol tapectl_test_facts_seam (nm), and
#   the string TAPECTL_TEST_FACTS (the environment variable the seam reads).
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
  if nm "$1" 2>/dev/null | grep -q tapectl_test_facts_seam; then echo "    symbol tapectl_test_facts_seam"; found=1; fi
  if LC_ALL=C grep -a -q TAPECTL_TEST_FACTS "$1"; then echo "    string TAPECTL_TEST_FACTS"; found=1; fi
  return $found
}

fails=0
nm "$TEST" >/dev/null 2>&1 || { echo "  FAIL  nm cannot read $TEST"; exit 1; }
if seam_free "$SHIPPED"; then echo "  ok    shipped $(basename "$SHIPPED") contains no test seam"
else echo "  FAIL  shipped $(basename "$SHIPPED") contains the test seam"; fails=1; fi
if seam_free "$TEST" >/dev/null; then echo "  FAIL  control: the check did not find the seam in $(basename "$TEST")"; fails=1
else echo "  ok    control: the same check finds the seam in $(basename "$TEST")"; fi
[ $fails -eq 0 ] && echo "PASS  test seam absent from the shipped binary" || { echo "FAIL  test seam check"; exit 1; }
