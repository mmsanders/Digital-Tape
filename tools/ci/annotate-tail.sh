#!/usr/bin/env bash
# Run a command; on failure, also raise its last lines as a GitHub error
# annotation, so the failure is readable from the checks API without the log.
#   annotate-tail.sh TITLE CMD [ARGS...]
set -uo pipefail
title=$1; shift
log=$(mktemp)
"$@" 2>&1 | tee "$log"
rc=${PIPESTATUS[0]}
if [ "$rc" -ne 0 ] && [ -n "${GITHUB_ACTIONS:-}" ]; then
  msg=$(tail -n 45 "$log" | tr -d '\r' | cut -c1-200 | sed -e 's/%/%25/g' | awk '{printf "%s%%0A", $0}')
  echo "::error title=${title} (exit ${rc})::${msg}"
fi
rm -f "$log"
exit "$rc"
