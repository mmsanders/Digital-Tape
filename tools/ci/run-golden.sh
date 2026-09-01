#!/usr/bin/env bash
# CI gate 5 — the golden suite. The cross-target contract.
#
# tests/ is owned outright by the Verification Lead (WP-10, WP-11), who reports
# to the PM. This runner is the CI wiring only. It does not define what correct
# sounds like, and the Software Lead does not get to edit what it compares against.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

echo "== gate: golden suite =="

fixtures=$(find tests/golden -name '*.wav' 2>/dev/null | wc -l | tr -d ' ')
runner=tests/golden/run.sh

if [ "$fixtures" -eq 0 ]; then
  echo "FAIL  no reference WAVs in tests/golden/"
  echo "      Expected until WP-10. These fixtures are the definition of correct"
  echo "      behaviour, not desktop tests firmware also happens to run — firmware"
  echo "      must be bit-identical at 1.0x playback."
  echo "      Owner: Verification Lead. Not assigned yet."
  exit 1
fi

if [ ! -x "$runner" ]; then
  echo "FAIL  $fixtures fixture(s) present but $runner is missing or not executable"
  exit 1
fi

exec "$runner"
