#!/usr/bin/env python3
"""Retained controls for the ruggedization protocol.

P1-R17-V-B02 and B03 are the reason this file exists. A protocol whose checks
have no instrument and no threshold cannot be executed by anyone but its
author, and a control described in prose has not been shown to fire. These
tests hold the protocol data to both properties, and then prove they can go red
by breaking the data on purpose.

What is enforced:

  every check carries an instrument, range, resolution, accuracy, calibration,
  baseline, a numeric threshold with a unit, and a disturbs flag;

  every control targets a real check, injects its defect in that check's own
  unit, and clears the threshold by at least MIN_MARGIN -- so a control cannot
  be a defect so small the check may legitimately miss it;

  the drop sequence is complete, ordered, non-repeating and named on the datum
  convention;

  the generated tables in spec/hw/ruggedization.md are not stale.

None of this executes a physical test. It checks that the method is executable
and auditable, which is what Verification asked for before anything is built.

    python3 test_protocol.py
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import protocol as P                                      # noqa: E402

MIN_MARGIN = 2.0          # an injected defect must be >= 2x the threshold


def every_check_is_executable() -> list[str]:
    bad = []
    for c in P.CHECKS:
        if c.direction not in ("max", "min"):
            bad.append(f"{c.id}: direction {c.direction!r} is not max or min, "
                       f"so a control's margin cannot be computed")
        for field in ("what", "instrument", "range_", "resolution", "accuracy",
                      "calibration", "baseline", "threshold", "unit", "when"):
            if not str(getattr(c, field)).strip():
                bad.append(f"{c.id}: {field} is empty")
        if not isinstance(c.limit, (int, float)) or c.limit <= 0:
            bad.append(f"{c.id}: limit {c.limit!r} is not a positive number")
        if c.unit not in c.threshold and c.unit != "actuations":
            bad.append(f"{c.id}: threshold {c.threshold!r} never states its "
                       f"unit {c.unit!r}")
        vague = [w for w in ("as before", "normal", "any opening", "same as",
                             "reasonable") if w in c.threshold.lower()]
        if vague:
            bad.append(f"{c.id}: threshold uses {vague} instead of a number")
    return bad


def every_control_clears_its_threshold() -> list[str]:
    bad = []
    for ctl in P.CONTROLS:
        target = P.CHECK_BY_ID.get(ctl.targets)
        if target is None:
            bad.append(f"{ctl.id}: targets {ctl.targets}, which is not a check")
            continue
        if ctl.unit != target.unit:
            bad.append(f"{ctl.id}: defect is in {ctl.unit}, {target.id}'s "
                       f"threshold is in {target.unit} -- not comparable")
            continue
        margin = target.margin(ctl.magnitude)
        if margin < MIN_MARGIN:
            bad.append(f"{ctl.id}: defect {ctl.magnitude} {ctl.unit} is only "
                       f"{margin:.2f}x past the {target.limit} {target.unit} "
                       f"threshold ({target.direction}); {MIN_MARGIN}x is the "
                       f"minimum")
        for field in ("defect", "detected_by", "if_it_passes", "safety"):
            if not str(getattr(ctl, field)).strip():
                bad.append(f"{ctl.id}: {field} is empty")
    return bad


def the_checks_that_matter_most_have_controls() -> list[str]:
    """Every check that can only fail silently must have a control.

    A check nobody has proven can go red is a check nobody should rely on. The
    ones listed here are the failures a functional test alone never sees.
    """
    must = {"D-01", "D-04", "D-14", "D-17"}
    covered = {c.targets for c in P.CONTROLS}
    missing = sorted(must - covered)
    return [f"no control targets {m}, which can fail silently" for m in missing]


def the_drop_sequence_is_complete_and_ordered() -> list[str]:
    seq = P.drop_sequence()
    bad = []
    steps = [d.step for d in seq]
    if steps != list(range(1, len(seq) + 1)):
        bad.append(f"steps are not 1..n in order: {steps}")
    names = [d.orientation for d in seq]
    if len(set(names)) != len(names):
        bad.append(f"an orientation appears twice: {names}")
    if not set(P.FACES) <= set(names) or not P.FACES:
        bad.append("not every face is dropped")
    face_idx = [i for i, n in enumerate(names) if n in P.FACES]
    corner_idx = [i for i, n in enumerate(names) if n in P.CORNERS]
    if not face_idx or not corner_idx:
        bad.append("the sequence is missing a whole family (faces or corners)")
    elif max(face_idx) > min(corner_idx):
        bad.append("corners are dropped before faces; severity must increase")
    for n in names:
        if n not in P.FACES and n not in P.EDGES and n not in P.CORNERS:
            bad.append(f"{n} is not named on the datum convention")
    return bad


def disturbing_checks_are_not_run_mid_sequence() -> list[str]:
    bad = []
    for c in P.CHECKS:
        if c.disturbs and "every drop" in c.when:
            bad.append(f"{c.id} disturbs the article but is scheduled after "
                       f"every drop, which changes what the next drop tests")
        if not c.disturbs and not c.when.strip():
            bad.append(f"{c.id}: no schedule")
    return bad


def the_spec_tables_are_current() -> list[str]:
    current = P.SPEC.read_text()
    if P.render(current) != current:
        return ["spec/hw/ruggedization.md is stale; run "
                "`python3 hardware/rugged/protocol.py`"]
    return []


# --- the controls' own controls ---------------------------------------------

def _with(seq, idx, **changes):
    items = list(seq)
    items[idx] = copy.replace(items[idx], **changes) if hasattr(copy, "replace") \
        else type(items[idx])(**{**items[idx].__dict__, **changes})
    return tuple(items)


def a_missing_threshold_is_caught() -> list[str]:
    saved = P.CHECKS
    try:
        P.CHECKS = _with(P.CHECKS, 0, threshold="as before", limit=0.2)
        if not every_check_is_executable():
            return ["a threshold of 'as before' passed the executability check"]
    finally:
        P.CHECKS = saved
    return []


def an_undersized_control_is_caught() -> list[str]:
    saved = P.CONTROLS
    try:
        # 0.21 mm against a 0.20 mm limit: technically over, nowhere near enough
        P.CONTROLS = _with(P.CONTROLS, 0, magnitude=0.21)
        problems = every_control_clears_its_threshold()
        if not problems:
            return ["a defect 1.05x the threshold passed the margin check"]
        if not any("C-1" in p for p in problems):
            return [f"the margin failure did not name C-1: {problems}"]
    finally:
        P.CONTROLS = saved
    return []


def a_control_in_the_wrong_unit_is_caught() -> list[str]:
    saved = P.CONTROLS
    try:
        P.CONTROLS = _with(P.CONTROLS, 0, unit="N")     # D-01's limit is in mm
        if not any("not comparable" in p
                   for p in every_control_clears_its_threshold()):
            return ["a defect measured in the wrong unit passed"]
    finally:
        P.CONTROLS = saved
    return []


def the_margin_check_stays_specific() -> list[str]:
    """An unrelated broken control must not hide the targeted one."""
    saved = P.CONTROLS
    try:
        P.CONTROLS = _with(_with(P.CONTROLS, 0, magnitude=0.21),
                           1, targets="D-99")           # unrelated breakage
        problems = every_control_clears_its_threshold()
        if not any("C-1" in p and "minimum" in p for p in problems):
            return [f"C-1's margin failure vanished when C-2 was also broken: "
                    f"{problems}"]
    finally:
        P.CONTROLS = saved
    return []


def an_out_of_order_sequence_is_caught() -> list[str]:
    saved = P.FACES
    try:
        P.FACES = {}      # no faces at all: corners would come first
        if not the_drop_sequence_is_complete_and_ordered():
            return ["a sequence with no face drops passed"]
    finally:
        P.FACES = saved
    return []


CONTROLS_SUITE = (
    every_check_is_executable,
    every_control_clears_its_threshold,
    the_checks_that_matter_most_have_controls,
    the_drop_sequence_is_complete_and_ordered,
    disturbing_checks_are_not_run_mid_sequence,
    the_spec_tables_are_current,
    a_missing_threshold_is_caught,
    an_undersized_control_is_caught,
    a_control_in_the_wrong_unit_is_caught,
    the_margin_check_stays_specific,
    an_out_of_order_sequence_is_caught,
)


def main() -> int:
    failures = []
    for c in CONTROLS_SUITE:
        for problem in c():
            failures.append(f"{c.__name__}: {problem}")
    if failures:
        for f in failures:
            print(f"FAIL rugged protocol: {f}", file=sys.stderr)
        return 1
    print(f"OK  rugged protocol: {len(CONTROLS_SUITE)} retained controls; "
          f"{len(P.CHECKS)} checks all carry instrument/baseline/threshold, "
          f"{len(P.CONTROLS)} injected defects all clear their threshold by "
          f">= {MIN_MARGIN}x, {len(P.drop_sequence())} ordered drops")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
