#!/usr/bin/env python3
"""Retained semantic controls for the sharp-point and sharp-edge screens.

P1-R19 asks for controls that "independently fail for altered probe
dimensions/age selection, force, travel/revolution/speed, tester geometry, tape
specification/conditioning and verdict thresholds". The word doing the work is
INDEPENDENTLY: a test that reads a constant out of the protocol and compares it
to itself passes no matter what the constant becomes.

So the expected values live here, written out a second time from the PM
primary-source note (`docs/REVIEW/P1-R21-CPSC-PRIMARY-SOURCE-NOTE.md`), and are
compared against the protocol's. Change a number in `sharp.py` and the
corresponding control goes red naming the field. That is the only arrangement in
which these controls mean anything.

P1-R21 widened that to **every new decision-driving source field**: the probe's
seven dimensions and its thread callout, the two things the drawing does NOT
state, the full tape specification, mandrel hardness and finish, the 90 +/- 5
degree axis angle, the worst-case orientation, insertion from every accessible
direction, the lit indicator, the access rules, the exemptions, the before/after
screening rule, the eCFR edition and currentness dates, and the 1500.50/.53
conditioning, drop, torque, tension and compression details.

Then the evaluators are exercised at and around each threshold, including one
directionally measured red control per family -- a reference sharp artifact for
points and a reference blade for edges -- because a screen that has never
indicated on a known-sharp specimen has not been shown to indicate at all.

Nothing here is a physical test, and nothing here is regulatory verification.
These controls prove internal consistency, provenance honesty and sensitivity.
They do not make the screen a determination and they cannot accept it.

    python3 test_sharp.py
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import protocol as P                                       # noqa: E402
import sharp as S                                          # noqa: E402

# --- the independent restatement --------------------------------------------
# Transcribed a second time from the PM primary-source note, deliberately NOT by
# importing from sharp.py. A mismatch means one of the two is wrong, and either
# way the screen stops.

NOTE = "docs/REVIEW/P1-R21-CPSC-PRIMARY-SOURCE-NOTE.md"

EXPECTED_ACCESS = {
    "probe for this product": "Probe B",
    "opening smaller than the collar": "insert to the collar",
    "opening larger than the collar but under 9.00 in":
        "insert WITH THE EXTENSION in any direction, up to 2.25x the "
        "opening's minor dimension",
    "opening 9.00 in or larger":
        "depth unrestricted, subject to any sub-openings encountered",
    "adjacent-gap exemption":
        "a gap no greater than 0.020 in is inaccessible without probe testing",
}

EXPECTED_POINT = {
    "gaging slot opening": "0.040 in wide by 0.045 in long",
    "sensing head recess": "at least 0.015 in",
    "additional travel that identifies a sharp point": "0.005 in",
    "return-spring force opposing that travel": "0.5 lbf",
    "maximum insertion force": "1.00 lbf",
    "insertion directions": "from EVERY accessible direction",
    "sharp result": "a lit indicator",
}

EXPECTED_EDGE = {
    "mandrel diameter": "0.375 +/- 0.005 in",
    "mandrel material and hardness": "steel, at least Rockwell C 40",
    "mandrel surface":
        "roughness no greater than 16 microinches, with no scratches, nicks "
        "or burrs",
    "tape": "pressure-sensitive TFE high-temperature electrical insulation "
            "tape per MIL-I-23594B (1971)",
    "tape backing thickness": "0.0026 to 0.0035 in",
    "tape adhesive":
        "pressure-sensitive silicone polymer, nominal 0.003 in thick",
    "tape width": "not less than 1/4 in (6 mm)",
    "tape temperature during testing": "70 to 80 degF",
    "tape application":
        "one UNSTRETCHED layer around the full mandrel circumference, ends "
        "butted or overlapped no more than 0.10 in",
    "normal force": "up to 1.35 lbf",
    "mandrel axis angle to the edge": "90 +/- 5 degrees",
    "linear motion": "prevented; the mandrel rotates without translating",
    "orientation": "seek the WORST-CASE orientation of the edge",
    "rotation": "one complete revolution",
    "tangential velocity": "1.00 +/- 0.08 in/s",
    "cut length that identifies a sharp edge":
        "a complete cut at least 1/2 in (13 mm) long",
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

# CS-1, as the drawing prints it.
EXPECTED_PROBE_B = {
    "a — spherical radius": "0.170 in",
    "b": "0.340 in",
    "c": "1.510 in",
    "d — each of three articulated sections": "0.760 in",
    "e": "2.280 in",
    "f — collar/extension diameter": "1 1/2 in",
    "g — overall with extension": "27 25/32 in",
    "extension attachment thread": "3/8-16NC-2B THD (TYP)",
    "extension": "approximately 24 in overall, 4 in typical segment",
    "joint articulation": "every joint may rotate up to 90 degrees",
}

# What the drawing does NOT print. These must stay absences.
EXPECTED_NOT_STATED = {"general dimensional tolerance", "surface finish"}

# CS-3, the banner PM read.
EXPECTED_ECFR_UP_TO_DATE = "2026-09-17"
EXPECTED_ECFR_LAST_AMENDED = "2026-09-17"
EXPECTED_RETRIEVED = "2026-09-19"

# Restated independently from 16 CFR 1500.50 and 1500.53, the
# over-36-through-96-month band.
EXPECTED_ABUSE = {
    "age band selection": "the applicable band; the MOST STRINGENT band when "
                          "ages span bands or labelling is unclear",
    "units": "English units govern",
    "samples": "previously untested samples, except that TENSION FOLLOWS "
               "TORQUE on the same sample",
    "preconditioning": "at least 4 hours at 73 +/- 3 degF and 20 to 70 "
                       "percent relative humidity",
    "test start": "within 5 minutes after removal from conditioning",
    "assembly state": "as stated for the article, assembled or disassembled",
    "direction of application": "the most severe reasonable direction",
    "impact medium": "nominal 1/8 in type-IV vinyl-composition tile over at "
                     "least 2.5 in of concrete, impact area at least 3 sq ft",
    "drop test": "for toys under 10.0 +/- 0.01 lb: FOUR random-orientation "
                 "drops from 3 ft +/- 0.5 in, WITH EXAMINATION AFTER EVERY "
                 "DROP",
    "torque test": "4.0 +/- 0.2 in-lb, CLOCKWISE AND COUNTERCLOCKWISE, "
                   "applied within 5 s to 180 degrees or the torque limit, "
                   "held 10 s",
    "tension test": "15.0 +/- 0.5 lbf parallel and then perpendicular to the "
                    "major axis, each applied within 5 s and held 10 s, on "
                    "the same sample used for torque",
    "compression test": "30.0 +/- 0.5 lbf through a 1.125 +/- 0.015 in rigid "
                        "metal disc, applied within 5 s and held 10 s",
    "conditional methods": "the section's bite and flexure methods where "
                           "their application clauses are met",
}

CROSSWALK_MUST_COVER = {"drop height", "impact medium", "torque", "tension",
                        "compression", "preconditioning",
                        "conditional bite and flexure", "when the screen runs"}

EXPECTED_EXEMPTIONS = {"bicycles and cribs", "necessarily functional features",
                       "what this means for Digital-Tape"}


def _by_name(fields) -> dict:
    return {f.name: f.rendered() for f in fields}


def _compare(label, fields, expected) -> list[str]:
    bad = []
    got = _by_name(fields)
    for name, want in expected.items():
        if name not in got:
            bad.append(f"{label}: field {name!r} is missing from the protocol")
        elif got[name] != want:
            bad.append(f"{label}: {name!r} reads {got[name]!r}, the primary "
                       f"source gives {want!r}")
    for name in got:
        if name not in expected:
            bad.append(f"{label}: unreviewed field {name!r} was added to the "
                       f"protocol without a matching restatement here")
    return bad


def transcribed_values_match_the_independent_restatement() -> list[str]:
    return (_compare("accessibility", S.ACCESSIBILITY, EXPECTED_ACCESS)
            + _compare("point", S.POINT, EXPECTED_POINT)
            + _compare("edge", S.EDGE, EXPECTED_EDGE))


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


def the_provenance_is_pm_inspection_and_says_so() -> list[str]:
    """The chain of custody must stay exactly what it is: a transcription.

    Claiming a direct reading here would be a lie about a safety record, and
    describing the closed facts as blocked or awaiting access would be a stale
    one. Both directions fail.
    """
    bad = []
    for token in ("PM", "19 September 2026", NOTE):
        if token not in S.SOURCE:
            bad.append(f"the provenance no longer names {token!r}")
    if S.RETRIEVAL != S.SOURCE:
        bad.append("RETRIEVAL and SOURCE have diverged; there is one chain of "
                   "custody, not two")
    doc = (S.__doc__ or "")
    for stale in ("merely assigned", "awaiting access", "not achieved",
                  "NOT ACHIEVED"):
        if stale in doc or stale in S.SOURCE:
            bad.append(f"stale blocked-source language {stale!r} survives, but "
                       f"CS-1..CS-5 are closed for the method")
    if not Path(__file__).resolve().parents[2].joinpath(NOTE).exists():
        bad.append(f"{NOTE} does not exist, so the cited chain of custody "
                   f"cannot be followed")
    return bad


def the_edition_and_currentness_are_recorded() -> list[str]:
    """CS-3. A currency claim without its dates is not a currency claim."""
    bad = []
    if S.ECFR_UP_TO_DATE != EXPECTED_ECFR_UP_TO_DATE:
        bad.append(f"up-to-date banner reads {S.ECFR_UP_TO_DATE!r}, PM read "
                   f"{EXPECTED_ECFR_UP_TO_DATE!r}")
    if S.ECFR_LAST_AMENDED != EXPECTED_ECFR_LAST_AMENDED:
        bad.append(f"last-amended banner reads {S.ECFR_LAST_AMENDED!r}, PM "
                   f"read {EXPECTED_ECFR_LAST_AMENDED!r}")
    if S.RETRIEVED != EXPECTED_RETRIEVED:
        bad.append(f"retrieval date reads {S.RETRIEVED!r}, PM retrieved on "
                   f"{EXPECTED_RETRIEVED!r}")
    if S.RETRIEVED < S.ECFR_UP_TO_DATE:
        bad.append("the record claims retrieval before the edition it read")
    if "unofficial" not in S.ECFR_STATUS:
        bad.append("the eCFR's own authoritative-but-unofficial status is no "
                   "longer recorded")
    if "English units govern" not in S.GOVERNING_UNITS:
        bad.append("the governing-units rule no longer states that English "
                   "units govern under 1500.48(e) and 1500.49(f)")
    for key, src in S.SOURCES.items():
        if src["edition_current_through"] != EXPECTED_ECFR_UP_TO_DATE:
            bad.append(f"{key} claims edition "
                       f"{src['edition_current_through']!r}, not the banner "
                       f"PM read")
    if "NOT CPSC approval" not in S.DISCLAIMER:
        bad.append("the disclaimer no longer denies CPSC approval")
    return bad


def no_field_claims_a_reading_it_did_not_make() -> list[str]:
    """Every field is a transcription of PM's reading, not our own."""
    bad = []
    for f in S.ACCESSIBILITY + S.POINT + S.EDGE + S.PROBE_B + S.USE_AND_ABUSE:
        if f.verified_primary:
            bad.append(f"{f.name!r} claims primary verification; no official "
                       f"host is reachable from this environment and the "
                       f"value is transcribed from PM's inspection")
        if not f.cite.startswith("16 CFR 15"):
            bad.append(f"{f.name!r} is not cited to an adopted section: "
                       f"{f.cite!r}")
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
    if not S.point_is_sharp(True, POINT_TRAVEL_IN):
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
    for v in (EDGE_TAPE_IN[0], EDGE_TAPE_IN[1]):
        if S.edge_run_conforms(**{**ok, "tape_thickness_in": v}):
            bad.append(f"tape backing {v} in is inside 0.0026-0.0035 and must "
                       f"pass")
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


def the_tape_specification_is_complete() -> list[str]:
    """CS-2. A consumable half-specified is a consumable unspecified.

    Every clause the section states about the tape must be present, because a
    tape that is the wrong width, applied stretched, or run at the wrong
    temperature changes the verdict and would do so silently.
    """
    got = _by_name(S.EDGE)
    bad = []
    required = {
        "tape": "MIL-I-23594B",
        "tape backing thickness": "0.0026",
        "tape adhesive": "silicone",
        "tape width": "1/4",
        "tape temperature during testing": "70 to 80",
        "tape application": "UNSTRETCHED",
    }
    for name, token in required.items():
        if name not in got:
            bad.append(f"the tape specification has lost {name!r}")
        elif token not in got[name]:
            bad.append(f"{name!r} no longer states {token!r}: {got[name]!r}")
    application = got.get("tape application", "")
    for token in ("full mandrel circumference", "butted", "0.10 in"):
        if token not in application:
            bad.append(f"the tape application rule no longer states {token!r}")
    return bad


def the_mandrel_finish_is_not_confused_with_the_probe() -> list[str]:
    """16 microinches belongs to 1500.49's mandrel, and only to it."""
    bad = []
    mandrel = _by_name(S.EDGE).get("mandrel surface", "")
    if "16 microinch" not in mandrel:
        bad.append("the mandrel's 16 microinch finish is no longer recorded")
    if "Rockwell C 40" not in _by_name(S.EDGE).get(
            "mandrel material and hardness", ""):
        bad.append("the mandrel's minimum Rockwell C 40 hardness is no longer "
                   "recorded")
    for f in S.PROBE_B:
        if "microinch" in f.rendered() or "Rockwell" in f.rendered():
            bad.append(f"probe field {f.name!r} has acquired a mandrel "
                       f"property ({f.rendered()!r}); the drawing states no "
                       f"probe finish and the two must not be conflated")
    return bad


def the_absences_stay_absences() -> list[str]:
    """The drawing prints no probe tolerance and no probe finish.

    Recording that is the whole point. A later round that quietly fills either
    in would be inventing a tolerance for a safety probe, so this fails both
    when an absence is dropped and when a probe field acquires one.
    """
    bad = []
    recorded = {what for what, _ in S.PROBE_B_NOT_STATED}
    for missing in sorted(EXPECTED_NOT_STATED - recorded):
        bad.append(f"the drawing's silence on {missing!r} is no longer "
                   f"recorded as an absence")
    for what, why in S.PROBE_B_NOT_STATED:
        if not why.strip():
            bad.append(f"the absence {what!r} states no consequence")
    for f in S.PROBE_B:
        rendered = f.rendered()
        if "+/-" in rendered or "tolerance" in rendered.lower():
            bad.append(f"probe field {f.name!r} has acquired a tolerance "
                       f"({rendered!r}); the drawing prints none")
    return bad


def the_probe_dimensions_are_what_the_drawing_prints() -> list[str]:
    """Altering a probe dimension must fail against an independent restatement."""
    bad = _compare("probe", S.PROBE_B, EXPECTED_PROBE_B)
    thread = _by_name(S.PROBE_B).get("extension attachment thread", "")
    if thread != "3/8-16NC-2B THD (TYP)":
        bad.append(f"the extension thread callout reads {thread!r}; the "
                   f"drawing labels it '3/8-16NC-2B THD (TYP)' and a "
                   f"paraphrase is not a callout")
    for f in S.PROBE_B:
        if "assignment" in f.cite:
            bad.append(f"probe {f.name}: the citation still says the value "
                       f"came via the assignment; it is now transcribed from "
                       f"PM's inspection of the drawing")
    return bad


def the_use_and_abuse_conditions_are_the_seven_year_band() -> list[str]:
    bad = _compare("use and abuse", S.USE_AND_ABUSE, EXPECTED_ABUSE)
    for f in S.USE_AND_ABUSE:
        if "1500.5" not in f.cite:
            bad.append(f"{f.name!r} is not cited to 1500.50 or 1500.53")
    got = _by_name(S.USE_AND_ABUSE)
    # The details that change what a run means, named one by one.
    for name, token in (("drop test", "EXAMINATION AFTER EVERY DROP"),
                        ("drop test", "FOUR"),
                        ("drop test", "10.0 +/- 0.01 lb"),
                        ("torque test", "COUNTERCLOCKWISE"),
                        ("tension test", "perpendicular"),
                        ("tension test", "same sample used for torque"),
                        ("compression test", "1.125 +/- 0.015 in"),
                        ("preconditioning", "73 +/- 3 degF"),
                        ("preconditioning", "20 to 70 percent"),
                        ("test start", "5 minutes"),
                        ("age band selection", "MOST STRINGENT"),
                        ("direction of application", "most severe"),
                        ("impact medium", "type-IV vinyl-composition tile")):
        if token not in got.get(name, ""):
            bad.append(f"{name!r} no longer states {token!r}, which changes "
                       f"what the referenced condition is")
    return bad


def the_scope_and_exemptions_are_recorded() -> list[str]:
    """CS-4, including the one that is deliberately unavailable to us."""
    bad = []
    got = {what: effect for what, effect in S.EXEMPTIONS}
    for missing in sorted(EXPECTED_EXEMPTIONS - set(got)):
        bad.append(f"the exemption record has lost {missing!r}")
    functional = got.get("necessarily functional features", "")
    for token in ("label", "no nonfunctional sharp feature"):
        if token not in functional:
            bad.append(f"the functional exemption no longer states {token!r}, "
                       f"and it is conditional on both")
    ours = got.get("what this means for Digital-Tape", "")
    if "NO planned functional sharp point or edge" not in ours:
        bad.append("the record no longer states that the functional exemption "
                   "is unavailable to this product, which is the safer side "
                   "and must not be quietly reversed")
    for token in ("BEFORE and AFTER", "bite test"):
        if token not in S.WHEN_SCREENED:
            bad.append(f"the screening rule no longer states {token!r}")
    return bad


def the_crosswalk_states_every_gap() -> list[str]:
    """A crosswalk that quietly drops an uncovered test is worse than none."""
    items = {c[0] for c in S.CROSSWALK}
    bad = [f"the crosswalk no longer covers {m!r}"
           for m in sorted(CROSSWALK_MUST_COVER - items)]
    for item, ours, theirs, gap in S.CROSSWALK:
        if not gap.strip():
            bad.append(f"crosswalk row {item!r} states no gap")
        if ours.strip() == theirs.strip():
            bad.append(f"crosswalk row {item!r} claims our method and the "
                       f"referenced condition are identical")
    for name in ("torque", "tension", "compression",
                 "conditional bite and flexure", "preconditioning"):
        row = next((c for c in S.CROSSWALK if c[0] == name), None)
        if row and "not covered" not in row[3].lower():
            bad.append(f"the {name} row no longer says it is not covered, but "
                       f"the method still does not perform it")
        if row and "not performed" not in row[1].lower() and name in (
                "torque", "tension", "compression",
                "conditional bite and flexure"):
            bad.append(f"the {name} row no longer records that our method does "
                       f"not perform it")
    return bad


def the_source_questions_are_closed_for_the_method_only() -> list[str]:
    """CS-1..CS-5 closed; and closed must not be allowed to read as accepted."""
    closed = {cid for cid, _, _ in S.CLOSED}
    missing = {"CS-1", "CS-2", "CS-3", "CS-4", "CS-5"} - closed
    bad = [f"{m} is neither closed nor recorded" for m in sorted(missing)]
    open_ids = {cid for cid, _, _ in S.OPEN}
    for cid in sorted(closed & open_ids):
        bad.append(f"{cid} is recorded as both closed and open")
    cs5 = next((how for cid, _, how in S.CLOSED if cid == "CS-5"), "")
    if "Transcribed is not performed" not in cs5:
        bad.append("CS-5 no longer states that transcribing the use-and-abuse "
                   "method is not performing it")
    for cid, _, how in S.CLOSED:
        if "closed" not in how.lower():
            bad.append(f"{cid}'s disposition does not say what happened to it")
    return bad


def what_is_still_open_is_still_declared() -> list[str]:
    """RG-8..RG-10 are the real remaining gaps, and each must stay stated."""
    got = {cid: (what, why) for cid, what, why in S.OPEN}
    bad = [f"{m} was dropped from the open list without being closed"
           for m in sorted({"RG-8", "RG-9", "RG-10"} - set(got))]
    for cid, token in (("RG-8", "tester"), ("RG-9", "tolerance"),
                       ("RG-10", "regulatory")):
        what, why = got.get(cid, ("", ""))
        if token not in (what + why).lower():
            bad.append(f"{cid} no longer states its subject ({token})")
        if not why.strip():
            bad.append(f"{cid} states no consequence")
    return bad


def nothing_here_claims_compliance() -> list[str]:
    """The one claim this file must never make, checked as a claim.

    Closing the source questions makes the method exact. It does not make a
    pass a regulatory determination, and every place that could be read as one
    is required to deny it.
    """
    bad = []
    for token in ("NOT CPSC approval", "certification", "compliance",
                  "cannot accept its own screen"):
        if token not in S.DISCLAIMER:
            bad.append(f"the disclaimer no longer denies {token!r}")
    doc = (S.__doc__ or "")
    for token in ("not CPSC approval", "not a compliance claim"):
        if token not in doc:
            bad.append(f"the module docstring no longer states {token!r}")
    rg10 = next((w for cid, w, _ in S.OPEN if cid == "RG-10"), "")
    if "regulatory determination" not in rg10 and "regulatory" not in rg10:
        bad.append("RG-10 no longer states that our screen is not a "
                   "regulatory determination")
    return bad


# --- the controls' own negative controls ------------------------------------
# "A gate that never goes red has not established what it detects" (CLAUDE.md
# section 1). Every decision-driving source field closed in P1-R21 gets a
# mutation here: the field is altered the way a careless later round would
# alter it, and the control that guards it must go red AND name the field.
# This is retained, not a one-off demonstration -- if a control is ever
# weakened into always-green, this suite catches it on the next run.

def _field_with(seq, name, **changes):
    """Return `seq` with the Field called `name` altered."""
    out = []
    hit = False
    for f in seq:
        if f.name == name:
            out.append(dataclasses.replace(f, **changes))
            hit = True
        else:
            out.append(f)
    if not hit:
        raise KeyError(f"no field named {name!r} to mutate")
    return tuple(out)


def _field_without(seq, name):
    out = tuple(f for f in seq if f.name != name)
    if len(out) == len(seq):
        raise KeyError(f"no field named {name!r} to drop")
    return out


def _row_with(seq, key, idx, value):
    """Return `seq` with row `key`'s element `idx` replaced."""
    out = []
    hit = False
    for row in seq:
        if row[0] == key:
            row = row[:idx] + (value,) + row[idx + 1:]
            hit = True
        out.append(row)
    if not hit:
        raise KeyError(f"no row keyed {key!r} to mutate")
    return tuple(out)


# (what was broken, attribute, new value, guarding control, token the failure
#  must name). One row per decision-driving source field.
MUTATIONS = (
    ("a probe dimension", "PROBE_B",
     lambda: _field_with(S.PROBE_B, "c", value="1.500"),
     lambda: the_probe_dimensions_are_what_the_drawing_prints(), "c"),
    ("the extension thread callout", "PROBE_B",
     lambda: _field_with(S.PROBE_B, "extension attachment thread",
                         value="3/8 in coarse thread"),
     lambda: the_probe_dimensions_are_what_the_drawing_prints(), "thread"),
    ("the joint articulation", "PROBE_B",
     lambda: _field_with(S.PROBE_B, "joint articulation",
                         value="every joint may rotate up to 45 degrees"),
     lambda: the_probe_dimensions_are_what_the_drawing_prints(),
     "joint articulation"),
    ("an invented probe tolerance", "PROBE_B",
     lambda: _field_with(S.PROBE_B, "a — spherical radius",
                         value="0.170 +/- 0.001"),
     lambda: the_absences_stay_absences(), "tolerance"),
    ("a dropped absence", "PROBE_B_NOT_STATED",
     lambda: S.PROBE_B_NOT_STATED[:1],
     lambda: the_absences_stay_absences(), "surface finish"),
    ("the mandrel finish moved onto the probe", "PROBE_B",
     lambda: _field_with(S.PROBE_B, "b", value="0.340, 16 microinch finish"),
     lambda: the_mandrel_finish_is_not_confused_with_the_probe(), "microinch"),
    ("the mandrel hardness", "EDGE",
     lambda: _field_with(S.EDGE, "mandrel material and hardness",
                         value="steel"),
     lambda: the_mandrel_finish_is_not_confused_with_the_probe(), "Rockwell"),
    ("the mandrel surface finish", "EDGE",
     lambda: _field_with(S.EDGE, "mandrel surface", value="smooth"),
     lambda: the_mandrel_finish_is_not_confused_with_the_probe(), "microinch"),
    ("the tape width", "EDGE",
     lambda: _field_with(S.EDGE, "tape width", value="not less than 1/8 in"),
     lambda: the_tape_specification_is_complete(), "tape width"),
    ("the tape backing", "EDGE",
     lambda: _field_with(S.EDGE, "tape", value="TFE tape"),
     lambda: the_tape_specification_is_complete(), "MIL-I-23594B"),
    ("the tape adhesive", "EDGE",
     lambda: _field_with(S.EDGE, "tape adhesive", value="pressure-sensitive"),
     lambda: the_tape_specification_is_complete(), "silicone"),
    ("the tape conditioning temperature", "EDGE",
     lambda: _field_with(S.EDGE, "tape temperature during testing",
                         value="ambient", unit=""),
     lambda: the_tape_specification_is_complete(), "70 to 80"),
    ("stretched tape", "EDGE",
     lambda: _field_with(S.EDGE, "tape application",
                         value="one layer, pulled taut around the full "
                               "mandrel circumference, ends butted or "
                               "overlapped no more than 0.10 in"),
     lambda: the_tape_specification_is_complete(), "UNSTRETCHED"),
    ("the butt/overlap limit", "EDGE",
     lambda: _field_with(S.EDGE, "tape application",
                         value="one UNSTRETCHED layer around the full mandrel "
                               "circumference"),
     lambda: the_tape_specification_is_complete(), "0.10 in"),
    ("the mandrel axis angle", "EDGE",
     lambda: _field_with(S.EDGE, "mandrel axis angle to the edge",
                         value="90 +/- 15"),
     lambda: transcribed_values_match_the_independent_restatement(),
     "mandrel axis angle"),
    ("the worst-case orientation rule", "EDGE",
     lambda: _field_without(S.EDGE, "orientation"),
     lambda: transcribed_values_match_the_independent_restatement(),
     "orientation"),
    ("insertion from every accessible direction", "POINT",
     lambda: _field_with(S.POINT, "insertion directions",
                         value="from the most convenient direction"),
     lambda: transcribed_values_match_the_independent_restatement(),
     "insertion directions"),
    ("the lit indicator", "POINT",
     lambda: _field_without(S.POINT, "sharp result"),
     lambda: transcribed_values_match_the_independent_restatement(),
     "sharp result"),
    ("a probe access rule", "ACCESSIBILITY",
     lambda: _field_with(S.ACCESSIBILITY,
                         "opening larger than the collar but under 9.00 in",
                         value="insert to the collar"),
     lambda: transcribed_values_match_the_independent_restatement(), "2.25x"),
    ("the adjacent-gap exemption", "ACCESSIBILITY",
     lambda: _field_with(S.ACCESSIBILITY, "adjacent-gap exemption",
                         value="a gap no greater than 0.200 in is "
                               "inaccessible without probe testing"),
     lambda: transcribed_values_match_the_independent_restatement(),
     "adjacent-gap"),
    ("examination after every drop", "USE_AND_ABUSE",
     lambda: _field_with(S.USE_AND_ABUSE, "drop test",
                         value="for toys under 10.0 +/- 0.01 lb: FOUR "
                               "random-orientation drops from 3 ft +/- 0.5 in"),
     lambda: the_use_and_abuse_conditions_are_the_seven_year_band(),
     "EXAMINATION AFTER EVERY DROP"),
    ("the counterclockwise torque direction", "USE_AND_ABUSE",
     lambda: _field_with(S.USE_AND_ABUSE, "torque test",
                         value="4.0 +/- 0.2 in-lb, CLOCKWISE, applied within "
                               "5 s to 180 degrees or the torque limit, held "
                               "10 s"),
     lambda: the_use_and_abuse_conditions_are_the_seven_year_band(),
     "COUNTERCLOCKWISE"),
    ("the tension sample rule", "USE_AND_ABUSE",
     lambda: _field_with(S.USE_AND_ABUSE, "tension test",
                         value="15.0 +/- 0.5 lbf parallel and then "
                               "perpendicular to the major axis, each applied "
                               "within 5 s and held 10 s"),
     lambda: the_use_and_abuse_conditions_are_the_seven_year_band(),
     "same sample used for torque"),
    ("the compression disc", "USE_AND_ABUSE",
     lambda: _field_with(S.USE_AND_ABUSE, "compression test",
                         value="30.0 +/- 0.5 lbf through a 2.000 in rigid "
                               "metal disc, applied within 5 s and held 10 s"),
     lambda: the_use_and_abuse_conditions_are_the_seven_year_band(),
     "1.125 +/- 0.015 in"),
    ("the conditioning humidity", "USE_AND_ABUSE",
     lambda: _field_with(S.USE_AND_ABUSE, "preconditioning",
                         value="at least 4 hours at 73 +/- 3 degF"),
     lambda: the_use_and_abuse_conditions_are_the_seven_year_band(),
     "20 to 70 percent"),
    ("the impact medium", "USE_AND_ABUSE",
     lambda: _field_with(S.USE_AND_ABUSE, "impact medium",
                         value="bare concrete"),
     lambda: the_use_and_abuse_conditions_are_the_seven_year_band(),
     "type-IV vinyl-composition tile"),
    ("the most-stringent-band rule", "USE_AND_ABUSE",
     lambda: _field_with(S.USE_AND_ABUSE, "age band selection",
                         value="the applicable band"),
     lambda: the_use_and_abuse_conditions_are_the_seven_year_band(),
     "MOST STRINGENT"),
    ("an exemption", "EXEMPTIONS",
     lambda: S.EXEMPTIONS[:1],
     lambda: the_scope_and_exemptions_are_recorded(),
     "necessarily functional features"),
    ("the functional exemption's label condition", "EXEMPTIONS",
     lambda: _row_with(S.EXEMPTIONS, "necessarily functional features", 1,
                       "a sharp point or edge that is NECESSARILY functional "
                       "is exempt"),
     lambda: the_scope_and_exemptions_are_recorded(), "label"),
    ("the before/after screening rule", "WHEN_SCREENED",
     lambda: "Both methods screen accessible hazards after the referenced "
             "use-and-abuse tests.",
     lambda: the_scope_and_exemptions_are_recorded(), "BEFORE and AFTER"),
    ("the eCFR edition date", "ECFR_UP_TO_DATE", lambda: "2026-09-30",
     lambda: the_edition_and_currentness_are_recorded(), "up-to-date banner"),
    ("the last-amended date", "ECFR_LAST_AMENDED", lambda: "2026-01-01",
     lambda: the_edition_and_currentness_are_recorded(), "last-amended"),
    ("the eCFR's unofficial status", "ECFR_STATUS", lambda: "official",
     lambda: the_edition_and_currentness_are_recorded(), "unofficial"),
    ("the governing-units rule", "GOVERNING_UNITS",
     lambda: "metric values govern",
     lambda: the_edition_and_currentness_are_recorded(), "English units"),
    ("the chain of custody", "SOURCE",
     lambda: "read from the eCFR",
     lambda: the_provenance_is_pm_inspection_and_says_so(), "PM"),
    ("a revived blocked-source claim", "SOURCE",
     lambda: S.SOURCE + " -- primary-source transcription NOT ACHIEVED",
     lambda: the_provenance_is_pm_inspection_and_says_so(), "NOT ACHIEVED"),
    ("the compliance denial", "DISCLAIMER",
     lambda: "Internal engineering screen only.",
     lambda: nothing_here_claims_compliance(), "compliance"),
    ("CS-5's transcribed-is-not-performed warning", "CLOSED",
     lambda: _row_with(S.CLOSED, "CS-5", 2, "closed"),
     lambda: the_source_questions_are_closed_for_the_method_only(),
     "not performing it"),
    ("a source question closed and reopened at once", "OPEN",
     lambda: S.OPEN + (("CS-1", "Probe B geometry", "unrecovered"),),
     lambda: the_source_questions_are_closed_for_the_method_only(),
     "both closed and open"),
    ("a dropped open item", "OPEN", lambda: S.OPEN[:2],
     lambda: what_is_still_open_is_still_declared(), "RG-10"),
    ("a crosswalk gap talked away", "CROSSWALK",
     lambda: _row_with(S.CROSSWALK, "torque", 3, "equivalent in practice"),
     lambda: the_crosswalk_states_every_gap(), "not covered"),
    ("a dropped crosswalk row", "CROSSWALK",
     lambda: tuple(r for r in S.CROSSWALK if r[0] != "compression"),
     lambda: the_crosswalk_states_every_gap(), "compression"),
)


def every_source_control_goes_red_when_its_field_is_broken() -> list[str]:
    bad = []
    for label, attr, mutate, control, token in MUTATIONS:
        saved = getattr(S, attr)
        try:
            setattr(S, attr, mutate())
            problems = control()
            if not problems:
                bad.append(f"breaking {label} ({attr}) produced no failure; "
                           f"that control cannot detect what it guards")
            elif not any(token in p for p in problems):
                bad.append(f"breaking {label} ({attr}) failed without naming "
                           f"{token!r}: {problems}")
        finally:
            setattr(S, attr, saved)
    return bad


def the_suite_still_passes_after_every_mutation_is_undone() -> list[str]:
    """Restoration is part of the control: a leaked mutation would hide bugs."""
    return [f"a mutation leaked: {p}" for p in
            (transcribed_values_match_the_independent_restatement()
             + the_probe_dimensions_are_what_the_drawing_prints()
             + the_use_and_abuse_conditions_are_the_seven_year_band()
             + the_absences_stay_absences()
             + the_edition_and_currentness_are_recorded())]


CONTROLS_SUITE = (
    the_probe_dimensions_are_what_the_drawing_prints,
    the_absences_stay_absences,
    the_tape_specification_is_complete,
    the_mandrel_finish_is_not_confused_with_the_probe,
    the_use_and_abuse_conditions_are_the_seven_year_band,
    the_scope_and_exemptions_are_recorded,
    the_crosswalk_states_every_gap,
    the_provenance_is_pm_inspection_and_says_so,
    the_edition_and_currentness_are_recorded,
    nothing_here_claims_compliance,
    transcribed_values_match_the_independent_restatement,
    the_age_basis_is_probe_b_and_says_why,
    no_field_claims_a_reading_it_did_not_make,
    a_non_conforming_point_run_yields_no_verdict,
    the_point_criterion_is_the_travel_threshold,
    the_point_screen_indicates_on_a_known_sharp_artifact,
    a_non_conforming_edge_run_yields_no_verdict,
    the_edge_criterion_is_the_cut_length,
    the_edge_screen_cuts_on_a_known_sharp_blade,
    the_source_questions_are_closed_for_the_method_only,
    what_is_still_open_is_still_declared,
    every_source_control_goes_red_when_its_field_is_broken,
    the_suite_still_passes_after_every_mutation_is_undone,
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
    restated = (len(EXPECTED_ACCESS) + len(EXPECTED_POINT) + len(EXPECTED_EDGE)
                + len(EXPECTED_PROBE_B) + len(EXPECTED_ABUSE))
    print(f"OK  sharp screens: {len(CONTROLS_SUITE)} retained controls; "
          f"{restated} transcribed values independently restated; "
          f"{len(MUTATIONS)} source fields each demonstrated red by mutation; "
          f"point and edge families each have a measured red control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
