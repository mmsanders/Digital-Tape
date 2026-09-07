#!/usr/bin/env python3
"""Checks on the duplicate gate, and proof it can go red.

PM Decisions 007 §1 asked for a duplicate-geometry check because the plate review
found D, M and H are the same button and no slicer would ever have said so.

**The obvious version of this gate is useless, and that is the whole lesson.**
Every carrier has a different letter cut into its cap, so as shipped all nine are
distinct meshes. A check that compares solids runs GREEN on the exact plate that
prompted it. It is the allocation gate again (CLAUDE.md §1): the check measured a
real thing, and not the thing anyone cared about.

So the gate does two comparisons and this file proves each can fail:

  PARAMETER  two parts share the swept value with neither declared a control.
             This is what the PM was pointing at.
  MECHANISM  two parts are the same solid once the LABEL IS SUPPRESSED.
             This is what catches a parameter that never reached the geometry --
             two variants that differ on paper and are identical in the file.

    python3 test_packet.py            run the checks
    python3 test_packet.py --mutate   prove they can go red
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cartridge"))

import build_packet as bp     # noqa: E402
import latch                  # noqa: E402
import shell                  # noqa: E402

FAILED: list[str] = []


def check(ok: bool, what: str) -> None:
    if not ok:
        FAILED.append(what)
        print(f"  FAIL {what}")


# Set by --mutate. When true, entries() builds the parts AS SHIPPED, with their
# blind labels cut in -- which is what the obvious version of this gate would
# compare, and the reason that version is worthless.
NAIVE = False


def entries(variants=None, lids=True):
    variants = variants or latch.packet_01_variants()
    lab = NAIVE
    out = []
    for v in variants:
        out.append((f"carrier-{v.label}", ("hook_depth", v.hook_depth),
                    v.role == "bed-control", latch.carrier(v, label=lab).val()))
    for sv in shell.packet_variants():
        out.append((f"shell-base-{sv.label}", ("interference", sv.interference),
                    False, shell.base(sv, label=lab).val()))
        if lids:
            out.append((f"shell-lid-{sv.label}", ("lid", "common"), True,
                        shell.lid(sv.label if lab else "").val()))
    return out


def raises(fn) -> bool:
    try:
        fn()
    except SystemExit:
        return True
    return False


def run() -> int:
    # --- 1. the plate as designed passes ---------------------------------
    check(not raises(lambda: bp.check_duplicates(entries())),
          "the plate as designed has no undeclared duplicates")

    # --- 2. the label is what makes the naive check useless --------------
    # Every shipped carrier is a distinct mesh. State it as a check, because if
    # it ever stops being true the gate's whole design rationale changes.
    labelled = {bp.mechanism_signature(latch.carrier(v).val())
                for v in latch.packet_01_variants()}
    bare = {bp.mechanism_signature(latch.carrier(v, label=False).val())
            for v in latch.packet_01_variants()}
    check(len(labelled) == len(latch.packet_01_variants()),
          f"with labels, every carrier is a distinct solid ({len(labelled)} of 8) "
          "-- so a naive mesh comparison would pass")
    check(len(bare) < len(labelled),
          f"with labels suppressed, carriers collapse ({len(bare)} distinct) "
          "-- which is what the gate must see")

    # --- 3. PARAMETER red case -------------------------------------------
    # The failure the PM described: the generator collapses two sweep levels.
    vs = latch.packet_01_variants()
    collapsed = [replace(v, hook_depth=0.9) if v.label == "T" else v for v in vs]
    check(raises(lambda: bp.check_duplicates(entries(collapsed))),
          "RED: two variants sharing a swept value, neither declared, is caught")

    # --- 4. MECHANISM red case -------------------------------------------
    # A parameter that differs on paper and never reaches the geometry. Two
    # variants with distinct hook_depth values but identical solids.
    faked = [replace(v, hook_depth=1.2) if v.label == "T" else v for v in vs]
    faked = [replace(v, role="variant") for v in faked]
    check(raises(lambda: bp.check_duplicates(entries(faked))),
          "RED: parts identical once unlabelled, with different parameters, is caught")

    # --- 5. declaring a control must not be a blanket escape -------------
    # If declaring one part a control silenced the whole group, the gate would be
    # defeatable by a one-word edit.
    two_undeclared = [replace(v, role="variant") if v.label in ("D", "H") else v
                      for v in vs]
    check(raises(lambda: bp.check_duplicates(entries(two_undeclared))),
          "RED: undeclaring the bed controls is caught")

    # --- 6. position must not mask a duplicate ---------------------------
    import cadquery as cq
    a = latch.carrier(vs[0], label=False).val()
    b = a.moved(cq.Location(cq.Vector(97.0, 43.0, 0.0)))
    check(bp.mechanism_signature(a) == bp.mechanism_signature(b),
          "the same part at two bed positions hashes the same")

    n = 7
    if FAILED:
        print(f"\n{len(FAILED)} of {n} checks FAILED")
        return 1
    print(f"all {n} checks pass")
    return 0


def mutate() -> int:
    """The obvious gate: compare the parts as they ship, and skip the parameter
    check because the meshes "already prove it".

    This is not a straw man. It is the version most people would write, it is
    what "add a duplicate-geometry check" literally asks for, and **it passes on
    the exact plate that prompted the request** -- because the blind label that
    makes the experiment work also makes every part unique.
    """
    global NAIVE
    NAIVE = True
    original = bp.check_duplicates

    def naive(entries_):
        # Mechanism comparison only, on parts as shipped. No parameter check.
        return original([(n, ("naive", i), d, s)
                         for i, (n, _, d, s) in enumerate(entries_)])

    bp.check_duplicates = naive
    rc = run()
    if rc == 0:
        print("\nMUTATION SURVIVED -- the checks cannot go red. That is the bug.")
        return 1
    print("\nOK  mutation caught: a gate comparing parts as shipped is detected")
    return 0


if __name__ == "__main__":
    if "--mutate" in sys.argv:
        raise SystemExit(mutate())
    raise SystemExit(run())
