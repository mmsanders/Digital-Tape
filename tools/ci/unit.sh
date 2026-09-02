#!/usr/bin/env bash
# CI gate — Software Lead scaffolding self-tests.
#
# NOT acceptance. These verify the harness and the block-device ports, so that
# when a Verification Lead test fails it is failing on the engine rather than on
# my plumbing. Acceptance lives in tests/golden, tests/crash and tests/fuzz and
# is signed off by the Verification Lead only.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

echo "== gate: scaffolding self-tests =="
if make -C tests run; then
  echo "PASS  scaffolding self-tests"
  exit 0
fi
echo "FAIL  scaffolding self-tests"
exit 1
