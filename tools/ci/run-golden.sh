#!/usr/bin/env bash
# CI gate — the golden suite. Contract 3, the cross-target contract.
#
# Wiring only. tests/golden/ is the Verification Lead's: the fixtures and the
# manifest define correct behaviour, and nothing in this repo's scaffolding gets
# to decide what correct sounds like.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

echo "== gate: golden suite =="
exec tests/harness/run-golden.sh "$@"
