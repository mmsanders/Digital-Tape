#!/usr/bin/env bash
# CI gate 1 — the engine builds clean at -Werror.
set -uo pipefail
cd "$(dirname "$0")/../../engine" || exit 2

echo "== gate: build =="
if make all; then
  echo "PASS  engine builds"
  exit 0
fi
echo "FAIL  engine does not build"
echo "      Expected until WP-06. A guardrail that arrives after the code is"
echo "      advisory; a guardrail already failing is load-bearing."
exit 1
