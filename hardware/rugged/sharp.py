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
Every host serving the official text is blocked by this environment's network
egress proxy -- `ecfr.gov` answers 403 at the gateway, as do `govinfo.gov`,
`law.cornell.edu` and `cpsc.gov`. The operative values below were recovered by
web search against those same domains, which returns the regulation's own
wording but is a **secondary rendering, not the primary document**.

So every field carries its provenance, and `verified_primary` is False for all
of them. That is not a formality: it is the difference between "we transcribed
the rule" and "we recovered the rule's numbers through a search index", and a
safety screen should not blur it. What remains unrecoverable this way is listed
in OPEN and is not guessed -- the probe figure geometry in particular.
"""

from __future__ import annotations

from dataclasses import dataclass

RETRIEVED = "2026-09-19"
RETRIEVAL = ("web search restricted to ecfr.gov, law.cornell.edu, govinfo.gov "
             "and cpsc.gov; the documents themselves are unreachable from this "
             "environment (gateway 403 on CONNECT)")

SOURCES = {
    "1500.48": {
        "title": "Technical requirements for determining a sharp point in toys "
                 "and other articles intended for use by children under 8 years "
                 "of age",
        "cite": "16 CFR 1500.48",
        "url": "https://www.ecfr.gov/current/title-16/chapter-II/subchapter-C/"
               "part-1500/section-1500.48",
        "edition_current_through": None,   # the eCFR banner is not readable here
    },
    "1500.49": {
        "title": "Technical requirements for determining a sharp metal or glass "
                 "edge in toys and other articles intended for use by children "
                 "under 8 years of age",
        "cite": "16 CFR 1500.49",
        "url": "https://www.ecfr.gov/current/title-16/chapter-II/subchapter-C/"
               "part-1500/section-1500.49",
        "edition_current_through": None,
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


# --- accessibility (which features get tested at all) ------------------------

ACCESSIBILITY = (
    Field("probe for this product", "Probe B", "",
          "16 CFR 1500.48 — probe A for articles intended for children 3 years "
          "or less; probe B for over 3 up to 8 years",
          note="selected by the product's seven-year-old tiebreaker"),
    Field("adjacent-gap exemption", "0.020", "in",
          "16 CFR 1500.48 — a point is inaccessible without probe testing if it "
          "lies adjacent to a surface and the gap does not exceed 0.020 in "
          "(0.50 mm)"),
    Field("insertion depth, bounded openings", "up to 2.25x", "the opening's minor dimension",
          "16 CFR 1500.48 — for an opening whose minor dimension exceeds the "
          "probe collar diameter but is below the unrestricted threshold, the "
          "probe with its extension is inserted in any direction up to 2.25x "
          "the minor dimension, measured from any point in the plane of the "
          "opening"),
    Field("unrestricted-depth threshold, probe B", "9.00", "in",
          "16 CFR 1500.48 — 9.00 in (228.6 mm) or larger minor dimension with "
          "probe B; insertion depth is then unrestricted",
          note="probe A's equivalent threshold is 7.36 in (186.9 mm)"),
)

# --- the sharp-point tester --------------------------------------------------

POINT = (
    Field("gaging slot opening", "0.040 in wide by 0.045 in long", "",
          "16 CFR 1500.48 — rectangular opening 0.040 in (1.02 mm) wide by "
          "0.045 in (1.15 mm) long in the end of the slotted cap",
          note="Commission instruments use openings no greater than this"),
    Field("sensing head recess", "0.015", "in",
          "16 CFR 1500.48 — the sensing head is recessed 0.015 in (0.38 mm) "
          "below the end cap"),
    Field("additional travel that identifies a sharp point", "0.005", "in",
          "16 CFR 1500.48 — the point must move the sensing head a further "
          "0.005 in (0.12 mm)"),
    Field("return-spring force opposing that travel", "0.5", "lbf",
          "16 CFR 1500.48 — against the 0.5 lb (2.2 N) force of a return spring"),
    Field("maximum insertion force", "1.00", "lbf",
          "16 CFR 1500.48 — the force applied when inserting a point into the "
          "gaging slot is no more than 1.00 lb"),
)

# --- the sharp-edge tester ---------------------------------------------------

EDGE = (
    Field("mandrel diameter", "0.375 +/- 0.005", "in",
          "16 CFR 1500.49 — 0.375 +/- 0.005 in (9.35 +/- 0.12 mm)"),
    Field("tape", "single layer of polytetrafluoroethylene (TFE) tape wrapped "
          "around the full circumference", "",
          "16 CFR 1500.49 — contact between test edge and mandrel at the "
          "approximate centre of the tape width"),
    Field("tape backing thickness", "0.0026 to 0.0035", "in",
          "16 CFR 1500.49 — between 0.0026 in (0.066 mm) and 0.0035 in "
          "(0.089 mm)"),
    Field("normal force", "1.35", "lbf",
          "16 CFR 1500.49 — applied to the edge with a normal force of 1.35 lb "
          "(6.00 N)"),
    Field("rotation", "one", "complete revolution",
          "16 CFR 1500.49 — rotated through one complete revolution while the "
          "force against the edge is held constant"),
    Field("tangential velocity", "1.00 +/- 0.08", "in/s",
          "16 CFR 1500.49 — 1.00 +/- 0.08 in/s (25.4 +/- 2.0 mm/s) during the "
          "centre 75 percent of the rotation, with a smooth start and stop"),
    Field("cut length that identifies a sharp edge", "not less than 1/2 (0.5)", "in",
          "16 CFR 1500.49 — the edge is sharp if it completely cuts through the "
          "tape for a length of not less than 1/2 in (13 mm)"),
)

# --- what could not be recovered, and is therefore not stated ---------------

OPEN = (
    ("CS-1", "**Probe B's own geometry** — collar diameter, tip diameter and "
             "extension length from the section's figures. The selection rule "
             "and the depth rule are recovered; the probe's dimensions are not, "
             "because they live in a drawing rather than in text.",
     "blocks building or buying a conforming probe"),
    ("CS-2", "**Tape width** for the edge tester. The contact point is "
             "specified relative to the width; the width itself was not "
             "recovered.",
     "blocks specifying the consumable"),
    ("CS-3", "**The eCFR edition banner** — the 'current through' date. Nothing "
             "here can claim to be the current text.",
     "blocks any currency claim"),
    ("CS-4", "**The complete exclusion clauses** of both sections — which "
             "points and edges are exempt (functional features and similar).",
     "a screen that does not know its exclusions can only over-report, which is "
     "the safe direction, but it is not the method"),
    ("CS-5", "**The conditioning and use tests** referenced by the "
             "accessibility rule (1500.51/.52/.53, excluding the bite test), "
             "which determine whether a point is accessible before or after use "
             "and abuse.",
     "our sequence applies the screen after the abuse family, which is at least "
     "as severe; matching the referenced procedure exactly is not established"),
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
