#!/usr/bin/env bash
# Negative control for tools/fetch-evidence.sh's WP-11 assets (#366).
#
# Serves a fake release from a scratch directory over file:// and proves:
#   1. a declared asset whose bytes match its sha256 is installed;
#   2. one whose bytes do not match is REFUSED, exit non-zero, nothing installed;
#   3. a malformed declaration is refused.
# Touches only a scratch directory.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/rel/tag1" "$T/out"
printf 'golden reference bytes' > "$T/rel/tag1/ref.wav"
good=$(sha256sum "$T/rel/tag1/ref.wav" | cut -d' ' -f1)
bad=$(printf 'something else' | sha256sum | cut -d' ' -f1)
pass=0; fail=0
check() { if [ "$1" = yes ]; then echo "  ok    $2"; pass=$((pass+1)); else echo "  FAIL  $2"; fail=$((fail+1)); fi; }

echo "$good  $T/out/ref.wav  tag1  ref.wav" > "$T/assets"
FETCH_EVIDENCE_RELEASES="file://$T/rel" WP11_ASSETS="$T/assets" tools/fetch-evidence.sh wp11 >/dev/null 2>&1
[ $? -eq 0 ] && cmp -s "$T/out/ref.wav" "$T/rel/tag1/ref.wav" && r=yes || r=no
check $r "matching asset installed"

echo "$bad  $T/out/bad.wav  tag1  ref.wav" > "$T/assets"
FETCH_EVIDENCE_RELEASES="file://$T/rel" WP11_ASSETS="$T/assets" tools/fetch-evidence.sh wp11 >/dev/null 2>&1
[ $? -ne 0 ] && [ ! -e "$T/out/bad.wav" ] && r=yes || r=no
check $r "mismatched asset refused, nothing installed"

echo "nothex  $T/out/x.wav  tag1" > "$T/assets"
FETCH_EVIDENCE_RELEASES="file://$T/rel" WP11_ASSETS="$T/assets" tools/fetch-evidence.sh wp11 >/dev/null 2>&1
[ $? -ne 0 ] && [ ! -e "$T/out/x.wav" ] && r=yes || r=no
check $r "malformed declaration refused"

echo "== fetch-evidence WP-11 control: $pass passed, $fail broken =="
[ $fail -eq 0 ]
