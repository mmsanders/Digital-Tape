#!/bin/sh
# External evidence wrapper.
#
# tests/ops_draft8/runner.py builds its fixtures in a TemporaryDirectory and
# removes them on exit, so the exact VO08 input/output envelopes would not
# survive the run. This wrapper is passed as --adapter in place of the probe:
# it copies both envelopes into VT8_PRESERVE_DIR and then forwards the probe's
# stdout, stderr and exit status unchanged.
#
# It does not touch the runner, the oracle, any fixture or any assertion.
#
#   VT8_PROBE=/abs/path/vt8_ops_probe VT8_PRESERVE_DIR=/abs/path/evidence \
#     python3 runner.py --adapter /abs/path/preserve.sh --log ...

CASE="$1"; IN="$2"; OUT="$3"
: "${VT8_PROBE:?VT8_PROBE must name the real adapter executable}"
: "${VT8_PRESERVE_DIR:?VT8_PRESERVE_DIR must name a writable directory}"

mkdir -p "$VT8_PRESERVE_DIR" || exit 2
cp "$IN" "$VT8_PRESERVE_DIR/$CASE.in.vo08" || exit 2

"$VT8_PROBE" "$CASE" "$IN" "$OUT"
rc=$?

if [ -f "$OUT" ]; then
    cp "$OUT" "$VT8_PRESERVE_DIR/$CASE.out.vo08" || exit 2
fi
exit $rc
