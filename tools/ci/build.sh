#!/usr/bin/env bash
# CI gate 1 — the engine, the ports and the harness build clean at -Werror.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

echo "== gate: build =="
if ! make -C engine all; then
  echo "FAIL  engine or ports do not build"
  exit 1
fi
if ! make -C tests all; then
  echo "FAIL  test harness does not build"
  exit 1
fi
echo "PASS  engine, ports and harness build"
