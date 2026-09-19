#!/usr/bin/env python3
"""The sharp-point and sharp-edge internal screens, as executable data.

**This is an internal engineering screen. It is not CPSC approval, not
certification, not a compliance claim and not a safety acceptance.** It adopts
the method of two federal sections for our own use so that R-3 has a
deterministic answer instead of an opinion. A pass here says only that our own
screen found nothing; it says nothing about what a competent laboratory running
the real thing would find.

Adopted sources
---------------
  16 CFR 1500.48  sharp point, articles for children under 8 years of age
  16 CFR 1500.49  sharp metal or glass edge, same age scope

**Age basis.** The product's tiebreaker is a seven-year-old (CLAUDE.md section 1),
which is inside both sections' under-8 scope and above the 3-year boundary that
selects the accessibility probe. **Probe B** is therefore the applicable probe.
No product document places intended use under three; the Part 1501 small-parts
cylinder is adopted separately, on its own merits, and adopting it is not an
age claim.

Provenance, stated plainly
--------------------------
The official hosts are still refused by this environment's egress proxy. What
changed in P1-R21 is who looked: **PM retrieved and visually inspected the
current eCFR text and the three official Federal Register drawings on
19 September 2026** and published the exact details in
`docs/REVIEW/P1-R21-CPSC-PRIMARY-SOURCE-NOTE.md`.

So every value here is transcribed from a **PM-authenticated inspection of the
primary sources** -- not from a search index, and not from the documents opened
here. A retained control fails if this file ever describes itself as a direct
reading.

The eCFR describes itself as **authoritative but unofficial**, Title 16 up to
date as of 17 September 2026 and last amended the same day. **English units
govern** under 1500.48(e) and 1500.49(f); metric values are convenience
approximations, and where both appear the English value binds.

One thing the drawing does NOT say is recorded as carefully as the things it
does: it prints **no general dimensional tolerance and no surface-finish
requirement for the probe**. That is a fact about the source. Neither is
invented here, and a control fails if either is ever filled in.
"""

from __future__ import annotations

from dataclasses import dataclass

RETRIEVED = "2026-09-19"
# The sources are still unreachable FROM HERE -- ecfr.gov and
# img.federalregister.gov both answer 403 at this environment's egress gateway.
# What changed is who looked: PM retrieved and visually inspected the current
# eCFR text and all three official Federal Register drawings on 19 September
# 2026 and published the exact details. The values below are transcribed from
# that authenticated inspection, which is a real chain of custody and is stated
# as one rather than described as a direct reading.
SOURCE = ("PM inspection of the current eCFR text and the three official "
          "Federal Register drawings, 19 September 2026, published at "
          "docs/REVIEW/P1-R21-CPSC-PRIMARY-SOURCE-NOTE.md")
ECFR_UP_TO_DATE = "2026-09-17"      # banner: Title 16 up to date as of
ECFR_LAST_AMENDED = "2026-09-17"    # banner: Title 16 last amended
ECFR_STATUS = "authoritative but unofficial (the eCFR's own description)"
GOVERNING_UNITS = ("English units govern under 16 CFR 1500.48(e) and "
                   "1500.49(f); metric values are convenience approximations")
RETRIEVAL = SOURCE

SOURCES = {
    "1500.48": {
        "title": "Technical requirements for determining a sharp point in toys "
                 "and other articles intended for use by children under 8 years "
                 "of age",
        "cite": "16 CFR 1500.48",
        "url": "https://www.ecfr.gov/current/title-16/chapter-II/subchapter-C/"
               "part-1500/section-1500.48",
        "edition_current_through": ECFR_UP_TO_DATE,
    },
    "1500.49": {
        "title": "Technical requirements for determining a sharp metal or glass "
                 "edge in toys and other articles intended for use by children "
                 "under 8 years of age",
        "cite": "16 CFR 1500.49",
        "url": "https://www.ecfr.gov/current/title-16/chapter-II/subchapter-C/"
               "part-1500/section-1500.49",
        "edition_current_through": ECFR_UP_TO_DATE,
    },
}

DISCLAIMER = (
    "Internal engineering screen only. Adopted from the cited sections for our "
    "own design use. NOT CPSC approval, certification, regulatory compliance, "
    "third-party testing or safety acceptance. Hardware cannot accept its own "
    "screen, and a pass here is not a ruggedization result."
)


@dataclass(frozen=True)
class Field:
    """One operative value, and where it came from."""
    name: str
    value: float | tuple | str
    unit: str
    cite: str
    verified_primary: bool = False
    note: str = ""

    def rendered(self) -> str:
        if isinstance(self.value, tuple):
            return " to ".join(f"{v}" for v in self.value) + f" {self.unit}"
        return f"{self.value} {self.unit}" if self.unit else str(self.value)


# --- use-and-abuse conditioning for the seven-year band (CS-5) --------------

USE_AND_ABUSE = (
    Field("age band selection", "the applicable band; the MOST STRINGENT band "
          "when ages span bands or labelling is unclear", "",
          "16 CFR 1500.50"),
    Field("units", "English units govern", "", "16 CFR 1500.50"),
    Field("samples", "previously untested samples, except that TENSION FOLLOWS "
          "TORQUE on the same sample", "", "16 CFR 1500.50"),
    Field("preconditioning", "at least 4 hours at 73 +/- 3 degF and 20 to 70 "
          "percent relative humidity", "", "16 CFR 1500.50"),
    Field("test start", "within 5 minutes after removal from conditioning", "",
          "16 CFR 1500.50"),
    Field("assembly state", "as stated for the article, assembled or "
          "disassembled", "", "16 CFR 1500.50"),
    Field("direction of application", "the most severe reasonable direction",
          "", "16 CFR 1500.50"),
    Field("impact medium", "nominal 1/8 in type-IV vinyl-composition tile over "
          "at least 2.5 in of concrete, impact area at least 3 sq ft", "",
          "16 CFR 1500.53"),
    Field("drop test", "for toys under 10.0 +/- 0.01 lb: FOUR random-orientation "
          "drops from 3 ft +/- 0.5 in, WITH EXAMINATION AFTER EVERY DROP", "",
          "16 CFR 1500.53"),
    Field("torque test", "4.0 +/- 0.2 in-lb, CLOCKWISE AND COUNTERCLOCKWISE, "
          "applied within 5 s to 180 degrees or the torque limit, held 10 s",
          "", "16 CFR 1500.53"),
    Field("tension test", "15.0 +/- 0.5 lbf parallel and then perpendicular to "
          "the major axis, each applied within 5 s and held 10 s, on the same "
          "sample used for torque", "", "16 CFR 1500.53"),
    Field("compression test", "30.0 +/- 0.5 lbf through a 1.125 +/- 0.015 in "
          "rigid metal disc, applied within 5 s and held 10 s", "",
          "16 CFR 1500.53"),
    Field("conditional methods", "the section's bite and flexure methods where "
          "their application clauses are met", "", "16 CFR 1500.53"),
)

# --- crosswalk: the internal method against those conditions ----------------

CROSSWALK = (
    ("drop height", "1.00 m (+0/-10 mm)", "3 ft +/- 0.5 in (0.92 m)",
     "ours is ~9% higher. Severity in one dimension is not equivalence"),
    ("drop count and orientation", "12 declared orientations, cumulative",
     "4 random orientations, examination after EVERY drop",
     "neither contains the other: a random sequence lands where our twelve "
     "never do. We do examine after every drop, which matches"),
    ("impact medium", "bare concrete slab >= 50 mm",
     "nominal 1/8 in type-IV vinyl-composition tile over >= 2.5 in concrete, "
     "impact area >= 3 sq ft",
     "**a real gap.** Bare concrete is harder, so ours is a different test, "
     "not a stricter version of the same one"),
    ("article mass", "measured per article; planning estimate ~150 g",
     "the four-drop method applies to toys under 10.0 +/- 0.01 lb",
     "our article is far under that threshold, so the band applies"),
    ("torque", "not performed",
     "4.0 +/- 0.2 in-lb, clockwise AND counterclockwise, within 5 s to 180 "
     "degrees or the limit, held 10 s",
     "**not covered.** A part that only fails under torque passes our screen"),
    ("tension", "not performed",
     "15.0 +/- 0.5 lbf parallel then perpendicular, each within 5 s, held "
     "10 s, on the same sample used for torque",
     "**not covered**, same consequence"),
    ("compression", "not performed",
     "30.0 +/- 0.5 lbf through a 1.125 +/- 0.015 in rigid metal disc, within "
     "5 s, held 10 s",
     "**not covered**, same consequence"),
    ("conditional bite and flexure", "not performed",
     "the section's bite and flexure methods where their application clauses "
     "are met",
     "**not covered.** Whether their clauses would even be met here is not "
     "assessed"),
    ("preconditioning", "ambient recorded, not controlled",
     "at least 4 h at 73 +/- 3 degF and 20 to 70 percent RH, test started "
     "within 5 minutes of removal",
     "**not covered.** Our articles are not conditioned, and PLA's properties "
     "move with temperature -- so our result carries a variable the referenced "
     "method controls"),
    ("sample rules", "2 articles, each taking the full sequence",
     "previously untested samples, except tension follows torque on the same "
     "sample",
     "compatible in spirit; we run no torque or tension, so the exception does "
     "not arise"),
    ("shake and tumble", "3 Hz shake, 25 tumbles", "no direct equivalent",
     "ours goes beyond these conditions. Extra evidence, not compliance"),
    ("when the screen runs", "R-3/R-4 after the abuse families",
     "accessible hazards screened BEFORE and AFTER the referenced use-and-abuse "
     "tests, excluding the bite test",
     "**partially covered.** We screen after, not before, and our 'before' "
     "baseline is an inspection rather than the referenced screen"),
)

# --- Probe B's own geometry (CS-1, closed for the method) -------------------
#
# Transcribed from PM's visual inspection of the official Federal Register
# drawing on 19 September 2026, recorded in
# docs/REVIEW/P1-R21-CPSC-PRIMARY-SOURCE-NOTE.md. Seven dimensions, the
# extension thread callout exactly as the drawing labels it, the extension's
# overall and typical segment lengths, and the joint articulation. What the
# drawing does not print is recorded immediately below as an absence; nothing
# missing from the drawing is supplied from anywhere else.

PROBE_B = (
    Field("a — spherical radius", "0.170", "in",
          "16 CFR 1500.48 probe drawing (EC03OC91.056 / .058)"),
    Field("b", "0.340", "in", "16 CFR 1500.48 probe drawing"),
    Field("c", "1.510", "in", "16 CFR 1500.48 probe drawing"),
    Field("d — each of three articulated sections", "0.760", "in",
          "16 CFR 1500.48 probe drawing"),
    Field("e", "2.280", "in", "16 CFR 1500.48 probe drawing"),
    Field("f — collar/extension diameter", "1 1/2", "in",
          "16 CFR 1500.48 probe drawing"),
    Field("g — overall with extension", "27 25/32", "in",
          "16 CFR 1500.48 probe drawing"),
    Field("extension attachment thread", "3/8-16NC-2B THD (TYP)", "",
          "16 CFR 1500.48 probe drawing, as labelled"),
    Field("extension", "approximately 24 in overall, 4 in typical segment", "",
          "16 CFR 1500.48 probe drawing"),
    Field("joint articulation", "every joint may rotate up to 90 degrees", "",
          "16 CFR 1500.48 text"),
)

# Two things the drawing does NOT state. Recorded as absences, because an
# absence in a source is a fact about the source, and filling it in would be
# inventing a tolerance for a safety probe.
PROBE_B_NOT_STATED = (
    ("general dimensional tolerance",
     "the drawing prints none; do not infer one from the decimal places"),
    ("surface finish",
     "the drawing prints none for the probe. (The MANDREL in 1500.49 does have "
     "one -- 16 microinches -- and the two must not be conflated.)"),
)

# --- accessibility (which features get tested at all) ------------------------

ACCESSIBILITY = (
    Field("probe for this product", "Probe B", "",
          "16 CFR 1500.48 — probe A for 3 years or less, probe B for over 3 "
          "through 8 years",
          note="selected by the product's seven-year-old tiebreaker"),
    Field("opening smaller than the collar", "insert to the collar", "",
          "16 CFR 1500.48 probe access rules"),
    Field("opening larger than the collar but under 9.00 in",
          "insert WITH THE EXTENSION in any direction, up to 2.25x the "
          "opening's minor dimension", "", "16 CFR 1500.48 probe access rules"),
    Field("opening 9.00 in or larger",
          "depth unrestricted, subject to any sub-openings encountered", "",
          "16 CFR 1500.48 probe access rules"),
    Field("adjacent-gap exemption",
          "a gap no greater than 0.020 in is inaccessible without probe "
          "testing", "", "16 CFR 1500.48"),
)

# --- the sharp-point tester -------------------------------------------------

POINT = (
    Field("gaging slot opening", "0.040 in wide by 0.045 in long", "",
          "16 CFR 1500.48 — rectangular opening 0.040 in (1.02 mm) wide by "
          "0.045 in (1.15 mm) long in the end of the slotted cap",
          note="Commission instruments use openings no greater than this"),
    Field("sensing head recess", "at least 0.015", "in",
          "16 CFR 1500.48 — the sensing head is recessed AT LEAST 0.015 in "
          "(0.38 mm) below the end cap"),
    Field("additional travel that identifies a sharp point", "0.005", "in",
          "16 CFR 1500.48 — the point must move the sensing head a further "
          "0.005 in (0.12 mm)"),
    Field("return-spring force opposing that travel", "0.5", "lbf",
          "16 CFR 1500.48 — against the 0.5 lb (2.2 N) force of a return spring"),
    Field("maximum insertion force", "1.00", "lbf",
          "16 CFR 1500.48 — the force applied when inserting a point into the "
          "gaging slot is no more than 1.00 lb"),
    Field("insertion directions", "from EVERY accessible direction", "",
          "16 CFR 1500.48 — the point is inserted into the gaging slot from "
          "every accessible direction"),
    Field("sharp result", "a lit indicator", "",
          "16 CFR 1500.48 — the indicator lights when the sensing head is "
          "moved the further 0.005 in"),
)

# --- the sharp-edge tester ---------------------------------------------------

EDGE = (
    Field("mandrel diameter", "0.375 +/- 0.005", "in", "16 CFR 1500.49"),
    Field("mandrel material and hardness", "steel, at least Rockwell C 40", "",
          "16 CFR 1500.49"),
    Field("mandrel surface", "roughness no greater than 16 microinches, with no "
          "scratches, nicks or burrs", "", "16 CFR 1500.49"),
    Field("tape", "pressure-sensitive TFE high-temperature electrical "
          "insulation tape per MIL-I-23594B (1971)", "",
          "16 CFR 1500.49(e)"),
    Field("tape backing thickness", "0.0026 to 0.0035", "in",
          "16 CFR 1500.49(e)"),
    Field("tape adhesive", "pressure-sensitive silicone polymer, nominal "
          "0.003 in thick", "", "16 CFR 1500.49(e)"),
    Field("tape width", "not less than 1/4 in (6 mm)", "",
          "16 CFR 1500.49(e)"),
    Field("tape temperature during testing", "70 to 80", "degF",
          "16 CFR 1500.49(e)"),
    Field("tape application", "one UNSTRETCHED layer around the full mandrel "
          "circumference, ends butted or overlapped no more than 0.10 in", "",
          "16 CFR 1500.49(e)"),
    Field("normal force", "up to 1.35", "lbf",
          "16 CFR 1500.49 — applied normal to the mandrel axis"),
    Field("mandrel axis angle to the edge", "90 +/- 5", "degrees",
          "16 CFR 1500.49 — axis held to the edge or its tangent"),
    Field("linear motion", "prevented; the mandrel rotates without translating",
          "", "16 CFR 1500.49"),
    Field("orientation", "seek the WORST-CASE orientation of the edge", "",
          "16 CFR 1500.49"),
    Field("rotation", "one complete revolution", "", "16 CFR 1500.49"),
    Field("tangential velocity", "1.00 +/- 0.08", "in/s",
          "16 CFR 1500.49 — through the centre 75 percent of one revolution, "
          "smooth start and stop"),
    Field("cut length that identifies a sharp edge",
          "a complete cut at least 1/2 in (13 mm) long", "",
          "16 CFR 1500.49"),
)

# --- scope, exemptions and when the screen runs (CS-4) ----------------------

EXEMPTIONS = (
    ("bicycles and cribs",
     "bicycles, and full-size and non-full-size cribs governed by the named "
     "parts, are exempt from both sections"),
    ("necessarily functional features",
     "a sharp point or edge that is NECESSARILY functional is exempt when no "
     "nonfunctional sharp feature exists; a toy relying on this requires a "
     "conspicuous, legible, visible sales label. 1500.48 applies this to "
     "points, 1500.49 to metal or glass edges, and 1500.49 defines those "
     "material classes"),
    ("what this means for Digital-Tape",
     "the product has NO planned functional sharp point or edge, so the "
     "functional exemption is not a pass condition here -- it is simply "
     "unavailable, which is the safer side to be on"),
)

WHEN_SCREENED = (
    "Both methods screen accessible hazards BEFORE and AFTER the referenced "
    "use-and-abuse tests, excluding each section's bite test."
)

# --- source questions CS-1..CS-5, and what remains open ---------------------

# CS-1..CS-5 are CLOSED FOR THE METHOD by the P1-R21 PM note, which supplied
# every field this file needs. Closure is conditional and the condition is
# stated rather than implied: PM's own note says these close only after Hardware
# binds the exact method AND independent Verification accepts that head. This is
# the binding half. The acceptance half is not mine to sign.

CLOSED = (
    ("CS-1", "Probe B geometry",
     "closed. Seven dimensions, the 3/8-16NC-2B THD (TYP) extension thread, the "
     "~24 in extension with 4 in typical segment, and 90-degree joint "
     "articulation. The drawing states NO general dimensional tolerance and NO "
     "surface finish for the probe; both are recorded as absences and neither "
     "is invented"),
    ("CS-2", "edge consumable and apparatus",
     "closed. MIL-I-23594B (1971) TFE tape: 0.0026-0.0035 in backing, silicone "
     "adhesive nominal 0.003 in, width >= 1/4 in, 70-80 degF during testing, "
     "one unstretched layer butted or overlapped <= 0.10 in. Mandrel 0.375 "
     "+/- 0.005 in, >= Rockwell C 40, <= 16 microinch finish, no nicks"),
    ("CS-3", "currency",
     "closed. eCFR Title 16 up to date as of 2026-09-17, last amended "
     "2026-09-17, retrieved by PM 2026-09-19, authoritative but unofficial. "
     "No later edition is claimed"),
    ("CS-4", "scope and exemptions",
     "closed. Bicycle and crib exemptions; the necessarily-functional exemption "
     "with its labelling requirement; the before/after screening rule excluding "
     "the bite test; and the full Probe B access rules"),
    ("CS-5", "applicable use and abuse",
     "closed as TRANSCRIPTION. 1500.50 conditioning and sample rules and the "
     "full 1500.53 method are recorded -- and the crosswalk above states, per "
     "row, everything our internal method does NOT do. Transcribed is not "
     "performed"),
)

# What remains open is no longer about reaching the sources.
OPEN = (
    ("RG-8", "**No tester exists.** The point and edge testers, the probe and "
             "the tape are specified now and owned by nobody. Nothing is "
             "approved for purchase and no tester construction is authorized.",
     "the screens cannot be run at all"),
    ("RG-9", "**The probe has no stated tolerance**, so a fabricated probe "
             "cannot be shown to conform dimensionally -- only to match the "
             "nominal figures.",
     "a home-made probe is an approximation of unknown fidelity"),
    ("RG-10", "**The regulatory-method gaps in the crosswalk stand**: torque, "
              "tension, compression, conditional bite and flexure, the tile "
              "impact medium, and preconditioning.",
     "our screen is not, and does not become, a regulatory determination"),
)

# --- evaluation: deterministic, given a conforming run ----------------------

def point_run_conforms(insertion_force_lbf: float, slot_w_in: float,
                       slot_l_in: float, recess_in: float,
                       spring_lbf: float) -> list[str]:
    """Is this a valid sharp-point run? A non-conforming run has no verdict."""
    bad = []
    if insertion_force_lbf > 1.00:
        bad.append(f"insertion force {insertion_force_lbf} lbf exceeds the "
                   f"1.00 lbf maximum")
    if slot_w_in > 0.040 or slot_l_in > 0.045:
        bad.append(f"gaging slot {slot_w_in} x {slot_l_in} in exceeds the "
                   f"0.040 x 0.045 in maximum")
    if recess_in < 0.015:
        bad.append(f"sensing head recess {recess_in} in is below the 0.015 in "
                   f"minimum")
    if abs(spring_lbf - 0.5) > 1e-9:
        bad.append(f"return spring {spring_lbf} lbf is not the specified 0.5 lbf")
    return bad


def point_is_sharp(contacted_head: bool, additional_travel_in: float) -> bool:
    """Sharp iff the point reaches the head AND moves it the further 0.005 in."""
    return bool(contacted_head) and additional_travel_in >= 0.005


def edge_run_conforms(mandrel_in: float, tape_thickness_in: float,
                      force_lbf: float, revolutions: float,
                      velocity_in_s: float, smooth: bool) -> list[str]:
    """Is this a valid sharp-edge run?"""
    bad = []
    if not (0.370 <= mandrel_in <= 0.380):
        bad.append(f"mandrel {mandrel_in} in is outside 0.375 +/- 0.005 in")
    if not (0.0026 <= tape_thickness_in <= 0.0035):
        bad.append(f"tape backing {tape_thickness_in} in is outside "
                   f"0.0026-0.0035 in")
    if abs(force_lbf - 1.35) > 1e-9:
        bad.append(f"normal force {force_lbf} lbf is not the specified 1.35 lbf")
    if abs(revolutions - 1) > 1e-9:
        bad.append(f"{revolutions} revolutions is not the specified single "
                   f"complete revolution")
    if not (0.92 <= velocity_in_s <= 1.08):
        bad.append(f"tangential velocity {velocity_in_s} in/s is outside "
                   f"1.00 +/- 0.08 in/s")
    if not smooth:
        bad.append("rotation did not have a smooth start and stop")
    return bad


def edge_is_sharp(cut_length_in: float) -> bool:
    """Sharp iff the tape is completely cut for 0.5 in or more."""
    return cut_length_in >= 0.5
