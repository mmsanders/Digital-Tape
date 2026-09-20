#!/usr/bin/env python3
"""Fail-closed checks for print packet A1MINI-01.

Every value the plate depends on is restated here from its own source rather
than imported from the builder, because a check that reads a constant out of the
thing it checks passes whatever that constant becomes. The clasp sweep's steps
are read from `hardware/cad/cartridge/shell.py`, which is the sweep's real
source, so if the sweep is ever respecified this suite goes red rather than
silently calibrating for a sweep that no longer exists.

    python3 test_process_packet.py
    python3 test_process_packet.py --mutate-bed   # prove the bed check goes red
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "cartridge"))

import cadquery as cq                                          # noqa: E402
import build_process_packet as P                               # noqa: E402
import shell                                                   # noqa: E402

REPO = HERE.parents[2]
OUT = REPO / "hardware" / "packets" / "a1mini-01"

# Restated independently. The A1 Mini's nominal envelope, and margins chosen to
# be conservative rather than to be whatever the builder happens to use.
EXPECT_BED = (180.0, 180.0, 180.0)
EXPECT_MIN_MARGIN = 10.0
EXPECT_MAX_Z = 175.0
EXPECT_PIN_D = 8.00
EXPECT_CLEARANCES = (0.00, 0.05, 0.10, 0.15, 0.20, 0.25)


def the_envelope_is_the_a1_minis() -> list[str]:
    bad = []
    if (P.BED_X, P.BED_Y, P.BED_Z) != EXPECT_BED:
        bad.append(f"bed is {(P.BED_X, P.BED_Y, P.BED_Z)}, not {EXPECT_BED}")
    if P.MARGIN < EXPECT_MIN_MARGIN:
        bad.append(f"margin {P.MARGIN} mm is under the {EXPECT_MIN_MARGIN} mm "
                   f"this packet is supposed to keep")
    if P.MAX_Z > EXPECT_MAX_Z:
        bad.append(f"Z cap {P.MAX_Z} mm is above {EXPECT_MAX_Z} mm")
    return bad


def the_ladder_resolves_finer_than_the_sweep_it_calibrates() -> list[str]:
    """The whole point of the plate, checked as arithmetic.

    The clasp sweep's steps come from its own module. If the ladder's step is
    not finer than the sweep's, this plate cannot tell us whether the sweep is
    readable -- which is the only reason it exists.
    """
    bad = []
    sweep = sorted(shell.SWEEP_INTERFERENCE)
    sweep_step = min(b - a for a, b in zip(sweep, sweep[1:]))
    rungs = sorted(P.CLEARANCES_MM)
    ladder_step = max(b - a for a, b in zip(rungs, rungs[1:]))
    if ladder_step >= sweep_step - 1e-9:
        bad.append(f"the ladder's coarsest step is {ladder_step:.3f} mm and the "
                   f"clasp sweep's finest is {sweep_step:.3f} mm; a ladder no "
                   f"finer than the sweep cannot establish the sweep is legible")
    if tuple(rungs) != EXPECT_CLEARANCES:
        bad.append(f"rungs are {tuple(rungs)}, the independent restatement is "
                   f"{EXPECT_CLEARANCES}")
    if rungs[0] != 0.0:
        bad.append("the zero rung is gone; without a rung the pin is expected "
                   "NOT to enter, a ladder where everything fits has measured "
                   "nothing and is consistent with any clearance at all")
    if len(set(rungs)) != len(rungs):
        bad.append("two rungs have the same clearance")
    return bad


def the_pin_and_the_sockets_share_one_nominal() -> list[str]:
    bad = []
    if abs(P.PIN_D - EXPECT_PIN_D) > 1e-9:
        bad.append(f"pin is {P.PIN_D} mm, the restatement is {EXPECT_PIN_D} mm")
    if P.SOCKET_DEPTH <= P.PIN_LEN * 0.25:
        bad.append(f"socket depth {P.SOCKET_DEPTH} mm is too shallow for the "
                   f"{P.PIN_LEN} mm shank to seat meaningfully")
    ladder = P.fit_ladder()
    pin = P.fit_pin()
    if ladder.val().Volume() <= 0 or pin.val().Volume() <= 0:
        bad.append("ladder or pin has no volume")
    # The index cut must actually remove material, or the block reads backwards.
    plain = cq.Workplane("XY").box(
        P.LADDER_PITCH * len(P.CLEARANCES_MM) + 8.0, P.LADDER_W, P.LADDER_H,
        centered=(True, True, False))
    holes = plain.val().Volume() - ladder.val().Volume()
    if holes <= 0:
        bad.append("the ladder has no sockets cut into it")
    return bad


def the_mass_coupon_volume_is_exact() -> list[str]:
    """The scale reading is divided by this. A wrong volume is a wrong density."""
    want = P.MASS_X * P.MASS_Y * P.MASS_Z
    got = P.modelled_volume_mm3(P.mass_coupon())
    if abs(got - want) > 1e-6:
        return [f"modelled volume {got} mm^3 != {want} mm^3 from its own "
                f"dimensions"]
    if P.MASS_COUNT < 3:
        return [f"{P.MASS_COUNT} mass coupons cannot show a spread; three is "
                f"the minimum that distinguishes one odd print from a trend"]
    return []


def every_object_is_inside_the_bed(bed_x=None, bed_y=None) -> list[str]:
    """Both edges of both axes, per object, plus the Z cap."""
    bed_x = P.BED_X if bed_x is None else bed_x
    bed_y = P.BED_Y if bed_y is None else bed_y
    items = [("fit-ladder", P.fit_ladder().val()),
             ("fit-pin-1", P.fit_pin().val()),
             ("fit-pin-2", P.fit_pin().val())]
    for n in range(1, P.MASS_COUNT + 1):
        items.append((f"mass-coupon-{n}", P.mass_coupon().val()))
    placed = P.pack(items, bed_x=bed_x, bed_y=bed_y, margin=P.MARGIN, gap=P.GAP)
    ok, problems = P.validate(placed, bed_x=bed_x, bed_y=bed_y)
    bad = list(problems) if not ok else []
    for name, shape, *_ in placed:
        if shape.BoundingBox().zmax > P.MAX_Z + 1e-6:
            bad.append(f"{name}: taller than the {P.MAX_Z} mm cap")
    return bad


def the_committed_plate_matches_its_source() -> list[str]:
    """Michael downloads the file; he cannot run `make`. Rebuild must be identical."""
    before = {p.name: p.read_bytes() for p in sorted(OUT.rglob("*"))
              if p.is_file()}
    if not before:
        return ["no committed packet to compare against"]
    r = subprocess.run([sys.executable, str(HERE / "build_process_packet.py")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return [f"rebuild failed: {r.stderr.strip()}"]
    bad = []
    for p in sorted(OUT.rglob("*")):
        if not p.is_file():
            continue
        if p.name not in before:
            bad.append(f"{p.name} appeared on rebuild")
        elif before[p.name] != p.read_bytes():
            bad.append(f"{p.name} differs after a rebuild")

    # On-disk determinism is not the same claim as "what is committed is what
    # the source produces". Only the tracked files are what Michael downloads,
    # and per-part STLs are deliberately untracked (see .gitignore), so ask git
    # about the tracked ones specifically.
    g = subprocess.run(["git", "status", "--porcelain", "--", str(OUT)],
                       cwd=REPO, capture_output=True, text=True)
    if g.returncode != 0:
        bad.append(f"could not ask git about the packet: {g.stderr.strip()}")
    else:
        dirty = [ln for ln in g.stdout.splitlines() if ln and not ln.startswith("??")]
        if dirty:
            bad.append("committed packet files differ from the source's output: "
                       + "; ".join(dirty))
    return bad


CHECKS = (
    the_envelope_is_the_a1_minis,
    the_ladder_resolves_finer_than_the_sweep_it_calibrates,
    the_pin_and_the_sockets_share_one_nominal,
    the_mass_coupon_volume_is_exact,
    every_object_is_inside_the_bed,
    the_committed_plate_matches_its_source,
)


def prove_red() -> int:
    """A bed check that never rejects anything has not established the plate fits.

    Shrinking the bed to 40 mm must put objects outside it. If this comes back
    green the geometry check is decorative and the packet is unverified.
    """
    problems = every_object_is_inside_the_bed(bed_x=40.0, bed_y=40.0)
    if not problems:
        print("FAIL a1mini packet: a 40 x 40 mm bed accepted the plate; the "
              "bed check cannot detect an object off the bed", file=sys.stderr)
        return 1
    print(f"OK  a1mini packet: proven able to go red "
          f"({len(problems)} object(s) rejected on a 40 x 40 mm bed)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutate-bed", action="store_true",
                    help="only run the negative control")
    args = ap.parse_args()
    if args.mutate_bed:
        return prove_red()

    failures = []
    for c in CHECKS:
        for problem in c():
            failures.append(f"{c.__name__}: {problem}")
    if failures:
        for f in failures:
            print(f"FAIL a1mini packet: {f}", file=sys.stderr)
        return 1
    sweep = sorted(shell.SWEEP_INTERFERENCE)
    print(f"OK  a1mini packet: {len(CHECKS)} checks pass; "
          f"{len(P.CLEARANCES_MM)} ladder rungs at "
          f"{P.CLEARANCES_MM[1] - P.CLEARANCES_MM[0]:.2f} mm resolve the clasp "
          f"sweep's {min(b - a for a, b in zip(sweep, sweep[1:])):.2f} mm step; "
          f"committed plate matches source")
    return prove_red()


if __name__ == "__main__":
    raise SystemExit(main())
