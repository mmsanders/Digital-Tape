#!/bin/sh
# Fails if any spec file's content or revision drifts from spec/VERSION.md.
set -eu
cd "$(dirname "$0")/../.."
fail=0

# 1. Content hashes match the manifest.
awk -F'|' '/^\| `spec\// {
    gsub(/[` ]/,"",$2); gsub(/[` ]/,"",$4); print $4"  "$2
}' spec/VERSION.md > /tmp/spec-bundle.sha256
sha256sum -c /tmp/spec-bundle.sha256 || fail=1

# 2. All three revision strings are identical, and match the manifest.
want=$(sed -n 's/.*\*\*Bundle:\*\* \([A-Z0-9-]*\).*/\1/p' spec/VERSION.md | head -1)
for f in spec/tapefs-v1.md spec/engine-api.md spec/acceptance.md; do
    got=$(sed -n 's/^\*\*Revision:\*\* \([A-Z0-9-]*\).*/\1/p' "$f" | head -1)
    [ "$got" = "$want" ] || { echo "FAIL: $f is $got, bundle is $want"; fail=1; }
done

exit $fail
