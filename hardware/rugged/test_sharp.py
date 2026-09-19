#!/usr/bin/env python3
"""Retained semantic controls for the sharp-point and sharp-edge screens.

P1-R19 asks for controls that "independently fail for altered probe
dimensions/age selection, force, travel/revolution/speed, tester geometry, tape
specification/conditioning and verdict thresholds". The word doing the work is
INDEPENDENTLY: a test that reads a constant out of the protocol and compares it
to itself passes no matter what the constant becomes.

So the expected values live here, written out a second time from the adopted
sections, and are compared against the protocol's. Change a number in
`sharp.py` and the corresponding control goes red naming the field. That is the
only arrangement in which these controls mean anything.

Then the evaluators are exercised at and around each threshold, including one
directionally measured red control per family -- a reference sharp artifact for
points and a reference blade for edges -- because a screen that has never
indicated on a known-sharp specimen has not been shown to indicate at all.

Nothing here is a physical test, and nothing here is regulatory verification:
the values are a secondary retrieval (see `sharp.py`), and these controls prove
internal consistency and sensitivity, not currency.

    python3 test_sharp.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import protocol as P                                       # noqa: E402
import sharp as S                                          # noqa: E402

# --- the independent restatement --------------------------------------------
# Transcribed a second time from the adopted sections, deliberately NOT by
# importing from sharp.py. A mismatch means one of the two is wrong, and either
# way the screen stops.

EXPECTED_ACCESS = {
    "probe for this product": "Probe B",
    "adjacent-gap exemption": "0.020 in",
    "insertion depth, bounded openings": "up to 2.25x the opening's minor dimension",
    "unrestricted-depth threshold, probe B": "9.00 in",
}

EXPECTED_POINT = {
    "gaging slot opening": "0.040 in wide by 0.045 in long",
    "sensing head recess": "0.015 in",
    "additional travel that identifies a sharp point": "0.005 in",
    "return-spring force opposing that travel": "0.5 lbf",
    "maximum insertion force": "1.00 lbf",
}

EXPECTED_EDGE = {
    "mandrel diameter": "0.375 +/- 0.005 in",
    "tape backing thickness": "0.0026 to 0.0035 in",
    "normal force": "1.35 lbf",
    "rotation": "one complete revolution",
    "tangential velocity": "1.00 +/- 0.08 in/s",
    "cut length that identifies a sharp edge": "not less than 1/2 (0.5) in",
}

# The numbers the evaluators must enforce, restated independently.
POINT_TRAVEL_IN = 0.005
POINT_SPRING_LBF = 0.5
POINT_MAX_INSERTION_LBF = 1.00
POINT_SLOT_W_IN, POINT_SLOT_L_IN = 0.040, 0.045
POINT_RECESS_IN = 0.015
EDGE_MANDREL_IN = (0.370, 0.380)
EDGE_TAPE_IN = (0.0026, 0.0035)
EDGE_FORCE_LBF = 1.35
EDGE_REVOLUTIONS = 1
EDGE_VELOCITY_IN_S = (0.92, 1.08)
EDGE_CUT_IN = 0.5


EXPECTED_PROBE_B = {
    "a": "0.170 in", "b": "0.340 in", "c": "1.510 in", "d": "0.760 in",
    "e": "2.280 in", "f": "1 1/2 in", "g": "27 25/32 in",
}

# Restated independently from 16 CFR 1500.53, the over-36-through-96-month band.
EXPECTED_ABUSE = {
    "drop test": "4 drops from 3 ft +/- 0.5 in, random orientation",
    "torque test": "4 in-lb +/- 0.2 applied evenly over 5 s clockwise to 180 "
                   "degrees or until exceeded, held 10 s",
    "tension test": "15 lb +/- 0.5 applied evenly over 5 s, parallel then "
                    "perpendicular to the major axis, each held 10 s",
    "compression test": "30 lb +/- 0.5 applied evenly within 5 s through the "
                        "disc, held 10 s",
}

CROSSWALK_MUST_COVER = {"drop height", "impact surface", "torque", "tension",
                        "compression"}


def _by_name(fields) -> dict:
    return {f.name: f.rendered() for f in fields}


def transcribed_values_match_the_independent_restatement() -> list[str]:
    bad = []
    for label, fields, expected in (("accessibility", S.ACCESSIBILITY, EXPECTED_ACCESS),
                                    ("point", S.POINT, EXPECTED_POINT),
                                    ("edge", S.EDGE, EXPECTED_EDGE)):
        got = _by_name(fields)
        for name, want in expected.items():
            if name not in got:
                bad.append(f"{label}: field {name!r} is missing from the protocol")
            elif got[name] != want:
                bad.append(f"{label}: {name!r} reads {got[name]!r}, the adopted "
                           f"section gives {want!r}")
        for name in got:
            if name not in expected and name != "tape":
                bad.append(f"{label}: unreviewed field {name!r} was added to the "
                           f"protocol without a matching restatement here")
    return bad


def the_age_basis_is_probe_b_and_says_why() -> list[str]:
    """Altering the age selection must fail, in both directions."""
    bad = []
    probe = _by_name(S.ACCESSIBILITY).get("probe for this product")
    if probe != "Probe B":
        bad.append(f"probe is {probe!r}; the seven-year-old tiebreaker selects "
                   f"Probe B, and Probe A would be an under-three claim")
    cite = next(f.cite for f in S.ACCESSIBILITY
                if f.name == "probe for this product")
    for token in ("probe A", "3 years", "probe B", "8 years"):
        if token not in cite:
            bad.append(f"the probe citation no longer states {token!r}, so the "
                       f"selection rule cannot be checked against the source")
    return bad


def every_field_declares_unverified_provenance() -> list[str]:
    """No field may quietly claim primary verification we do not have."""
    bad = []
    for f in S.ACCESSIBILITY + S.POINT + S.EDGE:
        if f.verified_primary:
            bad.append(f"{f.name!r} claims primary verification, but no official "
                       f"host is reachable from this environment")
        if not f.cite.startswith("16 CFR 15"):
            bad.append(f"{f.name!r} is not cited to an adopted section: {f.cite!r}")
    for key, src in S.SOURCES.items():
        if src["edition_current_through"] is not None:
            bad.append(f"{key} claims an edition date; the eCFR banner was not "
                       f"readable and must not be asserted")
    if "NOT CPSC approval" not in S.DISCLAIMER:
        bad.append("the disclaimer no longer denies CPSC approval")
    return bad


# --- point family -----------------------------------------------------------

def a_non_conforming_point_run_yields_no_verdict() -> list[str]:
    ok = dict(insertion_force_lbf=0.9, slot_w_in=POINT_SLOT_W_IN,
              slot_l_in=POINT_SLOT_L_IN, recess_in=POINT_RECESS_IN,
              spring_lbf=POINT_SPRING_LBF)
    bad = []
    if S.point_run_conforms(**ok):
        bad.append(f"a conforming run was rejected: {S.point_run_conforms(**ok)}")
    for label, change, marker in (
            ("insertion force", {"insertion_force_lbf": 1.01}, "insertion force"),
            ("slot width", {"slot_w_in": 0.041}, "gaging slot"),
            ("slot length", {"slot_l_in": 0.046}, "gaging slot"),
            ("recess", {"recess_in": 0.014}, "recess"),
            ("spring", {"spring_lbf": 0.25}, "return spring")):
        problems = S.point_run_conforms(**{**ok, **change})
        if not problems:
            bad.append(f"an out-of-specification {label} produced a valid run")
        elif not any(marker in p for p in problems):
            bad.append(f"the {label} failure does not name {marker!r}: {problems}")
    return bad


def the_point_criterion_is_the_travel_threshold() -> list[str]:
    bad = []
    if S.point_is_sharp(True, POINT_TRAVEL_IN):
        pass
    else:
        bad.append(f"{POINT_TRAVEL_IN} in of travel must read SHARP -- the "
                   f"section says 'not less than'")
    if S.point_is_sharp(True, POINT_TRAVEL_IN - 0.0001):
        bad.append("travel below the threshold must not read SHARP")
    if S.point_is_sharp(False, 1.0):
        bad.append("a point that never contacts the sensing head cannot be "
                   "SHARP however far the head is pushed by something else")
    return bad


def the_point_screen_indicates_on_a_known_sharp_artifact() -> list[str]:
    """C-5, the directionally measured red control for the point family."""
    ctl = next((c for c in P.CONTROLS if c.targets == "D-19"), None)
    if ctl is None:
        return ["no control targets D-19; the point screen has never been shown "
                "to indicate on a known sharp point"]
    bad = []
    if not S.point_is_sharp(True, ctl.magnitude):
        bad.append(f"the reference artifact's {ctl.magnitude} in must read SHARP")
    check = P.CHECK_BY_ID["D-19"]
    if check.margin(ctl.magnitude) < 2.0:
        bad.append(f"C-5's {ctl.magnitude} in is only "
                   f"{check.margin(ctl.magnitude):.2f}x the {check.limit} in "
                   f"threshold")
    if abs(check.limit - POINT_TRAVEL_IN) > 1e-12:
        bad.append(f"D-19's threshold {check.limit} is not the adopted "
                   f"{POINT_TRAVEL_IN} in")
    return bad


# --- edge family ------------------------------------------------------------

def a_non_conforming_edge_run_yields_no_verdict() -> list[str]:
    ok = dict(mandrel_in=0.375, tape_thickness_in=0.0030,
              force_lbf=EDGE_FORCE_LBF, revolutions=EDGE_REVOLUTIONS,
              velocity_in_s=1.00, smooth=True)
    bad = []
    if S.edge_run_conforms(**ok):
        bad.append(f"a conforming run was rejected: {S.edge_run_conforms(**ok)}")
    for label, change, marker in (
            ("mandrel", {"mandrel_in": 0.385}, "mandrel"),
            ("tape", {"tape_thickness_in": 0.0050}, "tape backing"),
            ("force", {"force_lbf": 2.0}, "normal force"),
            ("revolutions", {"revolutions": 2}, "revolutions"),
            ("velocity", {"velocity_in_s": 1.5}, "tangential velocity"),
            ("smoothness", {"smooth": False}, "smooth start")):
        problems = S.edge_run_conforms(**{**ok, **change})
        if not problems:
            bad.append(f"an out-of-specification {label} produced a valid run")
        elif not any(marker in p for p in problems):
            bad.append(f"the {label} failure does not name {marker!r}: {problems}")
    # The tolerance edges themselves.
    for v in (EDGE_MANDREL_IN[0], EDGE_MANDREL_IN[1]):
        if S.edge_run_conforms(**{**ok, "mandrel_in": v}):
            bad.append(f"mandrel {v} in is inside 0.375 +/- 0.005 and must pass")
    for v in (EDGE_VELOCITY_IN_S[0], EDGE_VELOCITY_IN_S[1]):
        if S.edge_run_conforms(**{**ok, "velocity_in_s": v}):
            bad.append(f"velocity {v} in/s is inside 1.00 +/- 0.08 and must pass")
    return bad


def the_edge_criterion_is_the_cut_length() -> list[str]:
    bad = []
    if not S.edge_is_sharp(EDGE_CUT_IN):
        bad.append(f"a {EDGE_CUT_IN} in cut must read SHARP -- 'not less than'")
    if S.edge_is_sharp(EDGE_CUT_IN - 0.01):
        bad.append("a cut below the threshold must not read SHARP")
    return bad


def the_edge_screen_cuts_on_a_known_sharp_blade() -> list[str]:
    """C-6, the directionally measured red control for the edge family."""
    ctl = next((c for c in P.CONTROLS if c.targets == "D-20"), None)
    if ctl is None:
        return ["no control targets D-20; the edge screen has never been shown "
                "to cut on a known sharp edge"]
    bad = []
    if not S.edge_is_sharp(ctl.magnitude):
        bad.append(f"the reference blade's {ctl.magnitude} in must read SHARP")
    check = P.CHECK_BY_ID["D-20"]
    if check.margin(ctl.magnitude) < 2.0:
        bad.append(f"C-6's {ctl.magnitude} in is only "
                   f"{check.margin(ctl.magnitude):.2f}x the {check.limit} in "
                   f"threshold")
    if abs(check.limit - EDGE_CUT_IN) > 1e-12:
        bad.append(f"D-20's threshold {check.limit} is not the adopted "
                   f"{EDGE_CUT_IN} in")
    return bad


def what_is_missing_is_still_declared_missing() -> list[str]:
    """CS-1..CS-5 must not quietly disappear or acquire invented values."""
    ids = {cid for cid, _, _ in S.OPEN}
    missing = {"CS-1", "CS-2", "CS-3", "CS-4", "CS-5"} - ids
    bad = [f"{m} was dropped from the open list without being closed"
           for m in sorted(missing)]
    probe_gap = next((t for cid, t, _ in S.OPEN if cid == "CS-1"), "")
    if "Probe B" not in probe_gap:
        bad.append("CS-1 no longer records that Probe B's own geometry is "
                   "unrecovered, which is the one gap that stops a conforming "
                   "probe being built")
    return bad


def the_probe_dimensions_are_what_the_assignment_gave() -> list[str]:
    """Altering a probe dimension must fail against an independent restatement."""
    got = _by_name(S.PROBE_B)
    bad = []
    for name, want in EXPECTED_PROBE_B.items():
        if name not in got:
            bad.append(f"probe dimension {name!r} is missing")
        elif got[name] != want:
            bad.append(f"probe {name}: {got[name]!r}, the figure gives {want!r}")
    for f in S.PROBE_B:
        if "assignment" not in f.cite:
            bad.append(f"probe {f.name}: the citation no longer records that "
                       f"this came via the assignment rather than the figure")
    return bad


def the_use_and_abuse_conditions_are_the_seven_year_band() -> list[str]:
    got = _by_name(S.USE_AND_ABUSE)
    bad = []
    for name, want in EXPECTED_ABUSE.items():
        if name not in got:
            bad.append(f"{name!r} is missing from the recorded conditions")
        elif got[name] != want:
            bad.append(f"{name}: reads {got[name]!r}, 1500.53 gives {want!r}")
    for f in S.USE_AND_ABUSE:
        if "1500.5" not in f.cite:
            bad.append(f"{f.name!r} is not cited to 1500.50 or 1500.53")
        if "18 months" in f.cite or "36 months" in f.cite.replace(
                "over 36 through 96 months", ""):
            bad.append(f"{f.name!r} cites a different age band than the "
                       f"seven-year-old this product is for")
    return bad


def the_crosswalk_states_every_gap() -> list[str]:
    """A crosswalk that quietly drops an uncovered test is worse than none."""
    items = {c[0] for c in S.CROSSWALK}
    bad = [f"the crosswalk no longer covers {m!r}"
           for m in sorted(CROSSWALK_MUST_COVER - {i.split(" and ")[0] for i in items}
                           - items)]
    for item, ours, theirs, gap in S.CROSSWALK:
        if not gap.strip():
            bad.append(f"crosswalk row {item!r} states no gap")
        if ours.strip() == theirs.strip():
            bad.append(f"crosswalk row {item!r} claims our method and the "
                       f"referenced condition are identical")
    for name in ("torque", "tension", "compression"):
        row = next((c for c in S.CROSSWALK if c[0] == name), None)
        if row and "not covered" not in row[3].lower():
            bad.append(f"the {name} row no longer says it is not covered, but "
                       f"the method still does not perform it")
    return bad


def the_blocked_retrieval_is_still_declared() -> list[str]:
    bad = []
    if "NOT ACHIEVED" not in S.RETRY_RECORD:
        bad.append("the record no longer states that primary-source "
                   "transcription was not achieved")
    for host in ("ecfr.gov", "img.federalregister.gov"):
        if host not in S.RETRY_RECORD:
            bad.append(f"the retry record no longer names {host} as blocked")
    return bad


CONTROLS_SUITE = (
    the_probe_dimensions_are_what_the_assignment_gave,
    the_use_and_abuse_conditions_are_the_seven_year_band,
    the_crosswalk_states_every_gap,
    the_blocked_retrieval_is_still_declared,
    transcribed_values_match_the_independent_restatement,
    the_age_basis_is_probe_b_and_says_why,
    every_field_declares_unverified_provenance,
    a_non_conforming_point_run_yields_no_verdict,
    the_point_criterion_is_the_travel_threshold,
    the_point_screen_indicates_on_a_known_sharp_artifact,
    a_non_conforming_edge_run_yields_no_verdict,
    the_edge_criterion_is_the_cut_length,
    the_edge_screen_cuts_on_a_known_sharp_blade,
    what_is_missing_is_still_declared_missing,
)


def main() -> int:
    failures = []
    for c in CONTROLS_SUITE:
        for problem in c():
            failures.append(f"{c.__name__}: {problem}")
    if failures:
        for f in failures:
            print(f"FAIL sharp screen: {f}", file=sys.stderr)
        return 1
    print(f"OK  sharp screens: {len(CONTROLS_SUITE)} retained controls; "
          f"{len(EXPECTED_ACCESS) + len(EXPECTED_POINT) + len(EXPECTED_EDGE)} "
          f"transcribed values independently restated; point and edge families "
          f"each have a measured red control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
