#!/bin/sh
# Decompressing front-end for complete_probe.
#
# The package ships its fixtures gzipped and the runner passes its own
# fixtures/ directory straight through, so something has to inflate them. This
# does exactly that and nothing else: it builds a private temp tree shaped like
# the package (<tmp>/fixtures and <tmp>/input) so the probe's relative lookup of
# input/WP-08.md still resolves, writes RAW .vo08 images into it, and hands it on.
#
# It is deliberately NOT trusted. complete_probe re-hashes every raw image
# against fixture.json's own raw_sha256 and refuses on mismatch, so this wrapper
# cannot substitute fixture bytes; and it never touches observation.json or any
# PCM, so the probe stays the only producer of observations.
#
#   COMPLETE_PROBE=/abs/path/complete_probe complete_adapter.sh \
#       --fixture-dir <package>/fixtures --out-dir DIR

set -e
FIXDIR=""; OUTDIR=""
while [ $# -gt 0 ]; do
    case "$1" in
        --fixture-dir) FIXDIR="$2"; shift 2 ;;
        --out-dir)     OUTDIR="$2"; shift 2 ;;
        *) echo "unexpected argument: $1" >&2; exit 2 ;;
    esac
done
[ -n "$FIXDIR" ] && [ -n "$OUTDIR" ] || { echo "usage: --fixture-dir DIR --out-dir DIR" >&2; exit 2; }
: "${COMPLETE_PROBE:?COMPLETE_PROBE must name the built probe}"

PKG=$(cd "$FIXDIR/.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/p1r6-raw-XXXXXX")
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/fixtures" "$TMP/input"
cp "$FIXDIR/fixture.json" "$TMP/fixtures/fixture.json"
cp "$PKG/input/WP-08.md" "$TMP/input/WP-08.md"
for k in long one empty; do
    gzip -dc "$FIXDIR/$k.vo08.gz" > "$TMP/fixtures/$k.vo08"
done

exec "$COMPLETE_PROBE" --fixture-dir "$TMP/fixtures" --out-dir "$OUTDIR"
