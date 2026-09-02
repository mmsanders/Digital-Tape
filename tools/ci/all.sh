#!/usr/bin/env bash
# Every gate, in order, reporting all of them rather than stopping at the first.
set -uo pipefail
cd "$(dirname "$0")" || exit 2

gates=(build.sh audit-allocation.sh audit-indirect.sh audit-stack.py
       audit-memory.sh unit.sh run-golden.sh)
failed=()

for g in "${gates[@]}"; do
  if [[ $g == *.py ]]; then python3 "./$g"; else "./$g"; fi
  [ $? -ne 0 ] && failed+=("$g")
  echo
done

echo "======================================"
if [ ${#failed[@]} -eq 0 ]; then
  echo "all gates pass"
  exit 0
fi
echo "${#failed[@]}/${#gates[@]} gates failing:"
printf '  %s\n' "${failed[@]}"
exit 1
