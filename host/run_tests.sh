#!/usr/bin/env bash
# The host test suite (make -C host test). Run directly from bash on Windows,
# where mingw32-make would hand recipes to cmd.exe.
#   run_tests.sh BUILD_DIR [EXE_SUFFIX]
set -euo pipefail
cd "$(dirname "$0")"
B=$1; X=${2:-}
"$B/test_wav$X" "$B/test_wav.d"
"$B/test_port$X"
./smoke.sh "$B/tapectl$X" "$B/smoke"
./smoke_wp14.sh "$B/tapectl$X" "$B/tapectl-test$X" "$B/smoke_wp14"
./test_seam.sh "$B/tapectl$X" "$B/tapectl-test$X"
./trace_selfcheck.sh "$B/tapectl-test$X" "$B/trace"
