#!/usr/bin/env bash
# CI gate — KiCad electrical and design rule checks.
#
# Built for the Hardware Lead (PM Decisions 002-HW §2). It lives next to the
# engine gates because it is the same kind of thing: a check that runs the same
# way locally and in CI, and fails with a file and a reason.
#
# The point, in the charter's words, is so the Hardware Lead can run ERC and DRC
# itself "rather than proposing a board nobody checked".
#
# No boards yet: this skips cleanly and says so. It must never report PASS for
# an absent board -- a gate that cannot run must not look like a gate that ran.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

OUT=build/hardware
KICAD=${KICAD_CLI:-kicad-cli}

echo "== gate: hardware ERC/DRC =="

mapfile -t SCH < <(find hardware -name '*.kicad_sch' 2>/dev/null | sort)
mapfile -t PCB < <(find hardware -name '*.kicad_pcb' 2>/dev/null | sort)

if [ ${#SCH[@]} -eq 0 ] && [ ${#PCB[@]} -eq 0 ]; then
  echo "SKIP  no KiCad files under hardware/ yet"
  echo "      Wired and waiting. When board-rev-a lands, this runs without"
  echo "      further setup. Owner: Hardware Lead."
  exit 0
fi

if ! command -v "$KICAD" >/dev/null 2>&1; then
  echo "FAIL  $KICAD not found, but ${#SCH[@]} schematic(s) and ${#PCB[@]} board(s) exist"
  echo "      A board that cannot be checked must not pass silently."
  echo "      Install kicad-cli, or set KICAD_CLI to its path."
  exit 1
fi

mkdir -p "$OUT"
rc=0

for f in "${SCH[@]}"; do
  n=$(basename "$f" .kicad_sch)
  echo "  ERC  $f"
  if ! "$KICAD" sch erc --exit-code-violations \
        --severity-error --severity-warning \
        --output "$OUT/$n.erc.rpt" "$f" >"$OUT/$n.erc.log" 2>&1; then
    echo "  FAIL ERC violations in $f"
    sed 's/^/        /' "$OUT/$n.erc.rpt" 2>/dev/null | head -40
    rc=1
  fi
done

for f in "${PCB[@]}"; do
  n=$(basename "$f" .kicad_pcb)
  echo "  DRC  $f"
  # Unconnected nets are errors, not warnings: an unrouted UHS-I data line is
  # exactly the defect this gate exists to catch before fabrication.
  if ! "$KICAD" pcb drc --exit-code-violations \
        --severity-error --severity-warning \
        --schematic-parity \
        --output "$OUT/$n.drc.rpt" "$f" >"$OUT/$n.drc.log" 2>&1; then
    echo "  FAIL DRC violations in $f"
    sed 's/^/        /' "$OUT/$n.drc.rpt" 2>/dev/null | head -40
    rc=1
  fi
done

if [ $rc -eq 0 ]; then
  echo "PASS  ${#SCH[@]} schematic(s), ${#PCB[@]} board(s) clean"
else
  echo "      Reports in $OUT/"
fi
exit $rc
