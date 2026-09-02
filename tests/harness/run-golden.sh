#!/usr/bin/env bash
# Golden-suite runner. Software Lead scaffolding; the fixtures and the manifest
# are the Verification Lead's.
#
# Reads tests/golden/MANIFEST, runs each case, and compares the produced WAV
# against its reference byte for byte. Contract 3: the references ARE the
# definition of correct behaviour, and firmware must be bit-identical at 1.0x —
# so there is no tolerance to configure and none will be added.
#
# MANIFEST format: one case per line, tab- or whitespace-separated, # for
# comments. See tests/golden/MANIFEST.md for the full contract.
#
#   <case-name>  <reference.wav>  <command...>
#
# The command is run from the repository root and must write its output WAV to
# the path in $GOLDEN_OUT. A case that exits non-zero fails without comparison.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

MANIFEST=${MANIFEST:-tests/golden/MANIFEST}
DIFF=build/tests/golden_diff
OUTDIR=build/tests/golden
FILTER=${1:-}

if [ ! -x "$DIFF" ]; then
  echo "FAIL  $DIFF not built — run: make -C tests all"
  exit 1
fi
if [ ! -f "$MANIFEST" ]; then
  echo "FAIL  no $MANIFEST"
  echo "      The golden fixtures and their manifest are the Verification Lead's"
  echo "      (WP-10/WP-11). The runner, the comparison and the audible diff are"
  echo "      built and waiting; see tests/golden/MANIFEST.md for the contract."
  exit 1
fi

mkdir -p "$OUTDIR"
pass=0; fail=0; failed=()

while read -r name ref cmd; do
  case "$name" in ''|\#*) continue ;; esac
  if [ -n "$FILTER" ] && [[ $name != *"$FILTER"* ]]; then continue; fi

  if [ -z "${ref:-}" ] || [ -z "${cmd:-}" ]; then
    echo "  FAIL  $name — malformed manifest line (need: name reference command)"
    fail=$((fail+1)); failed+=("$name"); continue
  fi
  if [ ! -f "$ref" ]; then
    echo "  FAIL  $name — reference $ref not found"
    fail=$((fail+1)); failed+=("$name"); continue
  fi

  out="$OUTDIR/$name.actual.wav"
  dif="$OUTDIR/$name.diff.wav"
  rm -f "$out" "$dif"

  if ! GOLDEN_OUT="$out" sh -c "$cmd" > "$OUTDIR/$name.log" 2>&1; then
    echo "  FAIL  $name — case command exited non-zero"
    sed 's/^/          /' "$OUTDIR/$name.log" | tail -5
    fail=$((fail+1)); failed+=("$name"); continue
  fi
  if [ ! -f "$out" ]; then
    echo "  FAIL  $name — case produced no output at \$GOLDEN_OUT"
    fail=$((fail+1)); failed+=("$name"); continue
  fi

  if "$DIFF" "$ref" "$out" "$dif"; then
    echo "  pass  $name"
    pass=$((pass+1))
  else
    echo "  FAIL  $name"
    fail=$((fail+1)); failed+=("$name")
  fi
done < "$MANIFEST"

echo
if [ $((pass + fail)) -eq 0 ]; then
  echo "FAIL  manifest matched no cases${FILTER:+ (filter: $FILTER)}"
  exit 1
fi
if [ $fail -eq 0 ]; then
  echo "PASS  golden suite — $pass case(s), bit-identical"
  exit 0
fi
echo "FAIL  golden suite — $fail of $((pass + fail)) case(s) differ:"
printf '        %s\n' "${failed[@]}"
echo "      Difference WAVs in $OUTDIR — silence where output matches."
exit 1
