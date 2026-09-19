#!/usr/bin/env python3
"""The ruggedization protocol, as data a machine can check.

Verification rejected rev 0.1 as a test method (P1-R17-V-B01..B06). The
substance of the rejection was not that the numbers were wrong: it was that a
prose protocol cannot be held to its own promises. "Any opening", "normal
force" and "as before" are not thresholds, and a control described in a
sentence is not a control.

So the protocol lives here, as tables, and `test_protocol.py` enforces the
properties the findings asked for:

  every check names an instrument, a range, a resolution, an accuracy, a
  calibration action, a baseline and a QUANTITATIVE threshold in a stated unit
  -- and says whether performing it disturbs the article;

  every control injects a defect measured in that same unit, large enough to
  clear the threshold it targets by a margin, so it cannot quietly fail to fire;

  every drop orientation is named on a stated datum convention, and the
  sequence is ordered and complete.

The tables in `spec/hw/ruggedization.md` are generated from here, so the
document cannot drift from the data (the pattern `mech/clasp.py` established).

    python3 protocol.py            regenerate the spec tables
    python3 protocol.py --check    fail if the spec is stale
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SPEC = Path(__file__).resolve().parents[2] / "spec" / "hw" / "ruggedization.md"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sharp  # noqa: E402  the sourced sharp-point / sharp-edge screens

# --- the datum convention ---------------------------------------------------
#
# Right-handed, article-fixed. +Z is up through the control face in normal use,
# +Y is the direction the cartridge is inserted, +X completes the set. Every
# face, edge and corner below is named by that frame, so an orientation can be
# set on the bench without a photograph and audited without one.

AXES = "right-handed, article-fixed: +Z up through the control face, " \
       "+Y the cartridge insertion direction, +X = Y x Z"

FACES = {
    "F+Z": "control face (buttons up)",
    "F-Z": "base",
    "F+Y": "cartridge-slot face",
    "F-Y": "rear face",
    "F+X": "right side",
    "F-X": "left side",
}

# Corners are sign triples; edges are the two non-zero signs. Only the ones the
# sequence uses are named, and each says why it is in the family.
CORNERS = {
    "C(+X+Y+Z)": "nearest the cartridge latch and the control face",
    "C(-X+Y+Z)": "cartridge slot, opposite side",
    "C(+X-Y-Z)": "over the cell compartment",
    "C(-X-Y-Z)": "over the cell compartment, opposite side",
}
EDGES = {
    "E(+Y+Z)": "shell seam along the control face",
    "E(-Y-Z)": "shell seam over the cell compartment",
}


@dataclass(frozen=True)
class Drop:
    step: int
    orientation: str
    why: str


def drop_sequence() -> list[Drop]:
    """Faces, then edges, then corners. Cumulative on one article.

    Order is part of the method because severity accumulates: a corner drop
    onto an already-cracked rib is not the same test as a corner drop onto a
    sound one. Least severe first means a failure is attributable to the step
    that caused it.
    """
    out, n = [], 0
    for face, why in FACES.items():
        n += 1
        out.append(Drop(n, face, f"flat on the {why}"))
    for edge, why in EDGES.items():
        n += 1
        out.append(Drop(n, edge, why))
    for corner, why in CORNERS.items():
        n += 1
        out.append(Drop(n, corner, why))
    return out


# --- drop and rough-play parameters ----------------------------------------

DROP = {
    "height_m": 1.00,
    "height_tolerance_m": (+0.000, -0.010),   # 1.00 m, never less than 0.99
    "height_datum": "lowest point of the article to the impact surface, "
                    "measured with a steel rule against a plumbed mark",
    "surface": "bare concrete slab, >= 50 mm thick, flat within 1 mm over "
               "300 mm, no covering",
    "attitude_tolerance_deg": 5.0,
    "release": "hinged trapdoor release fixture: the article rests on two "
               "half-flaps held by a single latch, so both flaps fall away "
               "together and the article is not pushed, tipped or spun",
    "settle_s": 10.0,     # the article is left untouched after impact
    "articles_per_stage": 2,
    "screen_rule": "n=2 is a SCREEN, not a statistical claim. One failure on "
                   "either article fails the stage.",
}

SHAKE = {
    "displacement_mm": 150.0,
    "displacement_tolerance_mm": 25.0,
    "displacement_definition": "PEAK-TO-PEAK travel of the article's centre "
                               "of mass along the axis under test",
    "measured_how": "against a 10 mm-graduated scale fixed in the camera "
                    "frame, in the plane of motion, counted from video",
    "frequency_hz": 3.0,
    "frequency_tolerance_hz": 0.2,
    "frequency_verified_how": "cycle count from the same video divided by its "
                              "duration -- an audible metronome proves cadence "
                              "was available, not that it was followed",
    "grip": "held in one hand across the F+X/F-X faces, controls unobstructed, "
            "wrist neutral",
    "per_axis_s": 120.0,
    "bout_s": 30.0,       # feasibility: 4 x 30 s with 30 s rest, not 120 s solid
    "bouts_per_axis": 4,
    "rest_s": 30.0,
    "axes": ("X", "Y", "Z"),
    "feasibility": "120 s of continuous 3 Hz hand motion is not reliably "
                   "repeatable, so each axis is four 30 s bouts with 30 s "
                   "rest. If any bout falls outside the displacement or "
                   "frequency tolerance on review, that bout is repeated.",
}

TUMBLE = {
    "count": 25,
    "box_internal_mm": (400, 400, 400),
    "box_wall": "9 mm plywood, internal faces bare (no lining, no padding)",
    "one_tumble": "one 90 degree rotation of the box about a horizontal edge, "
                  "so the article falls from the upper face to the new floor",
    "fall_height_m": 0.40,
    "fall_height_basis": "internal box height; the article starts on the face "
                         "that becomes the ceiling",
    "rate_s_per_tumble": 2.0,
    "loading": "one article, unrestrained, box otherwise empty",
    "completion": "25 tumbles counted aloud on video, box opened, article "
                  "photographed in the position it came to rest",
}


# --- checks: what is measured, with what, against what ----------------------

@dataclass(frozen=True)
class Check:
    id: str
    what: str
    instrument: str
    range_: str
    resolution: str
    accuracy: str
    calibration: str
    baseline: str
    threshold: str
    unit: str
    limit: float          # the quantitative threshold, in `unit`
    direction: str        # "max": fails ABOVE limit. "min": fails BELOW limit.
    disturbs: bool        # does performing it disturb the article?
    when: str

    def margin(self, magnitude: float) -> float:
        """How far an injected defect of `magnitude` clears this threshold.

        A gap that fails when it grows and a torque that fails when it shrinks
        cannot use the same arithmetic. Getting this wrong would have let a
        0.10 N.m control against a 0.25 N.m floor look like a 0.4x margin
        instead of the 2.5x it is -- which is how a control quietly stops
        proving anything.
        """
        if self.direction == "max":
            return magnitude / self.limit
        return self.limit / magnitude if magnitude else float("inf")


CHECKS: tuple[Check, ...] = (
    Check("D-01", "cell retention: free travel of the cell dummy in its pocket",
          "dial indicator on a magnetic stand, article opened and fixtured",
          "0-10 mm", "0.01 mm", "+/-0.02 mm",
          "zeroed against a 1.000 mm gauge block before each session",
          "travel under a 5.0 N applied load, recorded per article at stage 0",
          "increase over baseline <= 0.20 mm", "mm", 0.20, "max", True,
          "stage 0, every third drop, end of sequence"),
    Check("D-04", "shell seam gap",
          "feeler gauge set", "0.05-1.00 mm", "0.05 mm", "+/-0.005 mm (set spec)",
          "blades checked against a micrometer annually; visually before use",
          "largest blade entering the seam at stage 0, per edge, recorded",
          "no blade 0.20 mm or larger enters where the baseline blade was "
          "smaller", "mm", 0.20, "max", False,
          "after every drop"),
    Check("D-07", "cartridge retention against withdrawal",
          "push-pull force gauge, hook adapter on the cartridge grip feature",
          "0-50 N", "0.05 N", "+/-0.5% of reading",
          "checked against a 2.00 kg reference mass before each session",
          "withdrawal force at stage 0, mean of three, per article",
          "within 30% of baseline, and never below 8.0 N", "N", 8.0, "min", True,
          "stage 0, end of each family"),
    Check("D-10", "connector retention",
          "push-pull force gauge in line with the connector axis",
          "0-50 N", "0.05 N", "+/-0.5% of reading",
          "checked against a 2.00 kg reference mass before each session",
          "unmate force at stage 0 on the DESIGNATED DISTURB ARTICLE only",
          "unmate force >= 0.50 x baseline; in-sequence articles use "
          "continuity and seating instead", "x baseline", 0.50, "min", True,
          "stage 0 and end of sequence, disturb article only"),
    Check("D-12", "transport alignment",
          "dial indicator against the latch-bar datum face",
          "0-10 mm", "0.01 mm", "+/-0.02 mm",
          "zeroed against a 1.000 mm gauge block before each session",
          "datum reading at stage 0 with the bar at rest, per article",
          "shift from baseline <= 0.15 mm", "mm", 0.15, "max", True,
          "stage 0, every third drop, end of sequence"),
    Check("D-14", "loose part inside: mass and audible impact",
          "balance for mass; quiet room (<= 35 dBA) and a 0.3 m listen for "
          "impacts, article rotated through all three axes twice",
          "0-500 g", "0.01 g", "+/-0.03 g",
          "checked against a 100.00 g class-M2 mass before each session",
          "assembled mass at stage 0, per article",
          "mass change <= 0.10 g AND no audible internal impact", "g", 0.10,
          "max", False, "after every drop and after every rough-play element"),
    Check("D-17", "fastener retention",
          "torque screwdriver, breakaway direction",
          "0.10-1.00 N.m", "0.01 N.m", "+/-6% of reading",
          "verified against a torque tester at the start of each session",
          "install torque 0.35 N.m, recorded per fastener at stage 0",
          "residual breakaway torque >= 0.25 N.m (70% of install). Measuring "
          "it releases the fastener, so it is re-torqued and recorded",
          "N.m", 0.25, "min", True, "stage 0, end of each family"),
    Check("D-19", "sharp point created by the trial (R-3), on the Probe B "
          "accessibility basis",
          "sharp-point tester per 16 CFR 1500.48: slotted cap, recessed sensing "
          "head, 0.5 lbf return spring, indicating circuit",
          "0-0.050 in travel", "0.001 in", "+/-0.0005 in",
          "gap set against a 0.015 in feeler before each session; indication "
          "confirmed on the reference sharp artifact (control C-5)",
          "no accessible sharp point at stage 0, recorded per article",
          "sharp if the point contacts the sensing head and moves it a further "
          "0.005 in; insertion force never above 1.00 lbf", "in", 0.005, "max",
          False, "after the drop family and after the rough-play family"),
    Check("D-20", "sharp metal or glass edge created by the trial (R-3)",
          "sharp-edge tester per 16 CFR 1500.49: 0.375 in mandrel wrapped with "
          "a single layer of TFE tape, 1.35 lbf normal force, one revolution",
          "0-2 in cut length", "0.01 in", "+/-0.02 in",
          "mandrel diameter and tape thickness checked before each session; "
          "cut confirmed on the reference blade (control C-6)",
          "no accessible sharp edge at stage 0, recorded per article",
          "sharp if the tape is completely cut for 0.5 in or more in one "
          "revolution", "in", 0.5, "max", False,
          "after the drop family and after the rough-play family"),
    Check("FC-02", "audio output, both channels",
          "USB audio interface, line input, 1 kHz reference tone from the "
          "article's test track, RMS over 5 s",
          "-60 to +6 dBu", "0.1 dB", "+/-0.2 dB",
          "interface input calibrated against a 1.000 Vrms source",
          "per-channel RMS at stage 0, article at its fixed volume setting",
          "within 1.0 dB of baseline on both channels, no dropout", "dB", 1.0,
          "max", False, "after every drop and every rough-play element"),
    Check("FC-03", "controls",
          "10 actuations per control, logged by the article's own firmware "
          "counter",
          "n/a", "1 actuation", "exact count",
          "counter zeroed before each check",
          "10 of 10 registered per control at stage 0",
          "10 of 10 registered, no double-fire, no dead press", "actuations",
          10.0, "min", False, "after every drop and every rough-play element"),
)

CHECK_BY_ID = {c.id: c for c in CHECKS}


# --- controls: defects large enough that the check cannot miss them ---------

@dataclass(frozen=True)
class Control:
    id: str
    targets: str          # check id
    defect: str           # what is done, in measured terms
    magnitude: float      # in the target check's unit
    unit: str
    detected_by: str      # what the reading must show
    if_it_passes: str     # what it means if the check does NOT go red
    safety: str


CONTROLS: tuple[Control, ...] = (
    Control("C-1", "D-01",
            "the cell-dummy retainer is fitted with its 0.60 mm shim removed "
            "and its fastener omitted, giving a measured free travel of "
            "0.60 mm +/- 0.05 against a 0.20 mm limit",
            0.60, "mm",
            "D-01 must read >= 0.55 mm of travel before any abuse",
            "D-01 cannot detect a loose cell, so the cell-retention check is "
            "invalid and no article may be exposed until it is redesigned",
            "inert dummy only; no cell, charged or otherwise"),
    Control("C-2", "D-04",
            "one shell fastener is backed out until a 0.45 mm feeler blade "
            "enters the seam, against a 0.20 mm limit",
            0.45, "mm",
            "D-04 must admit a 0.40 mm blade where the baseline admitted none",
            "the seam check is decorative and must be redefined before it is "
            "relied on",
            "no energy stored; the article is not dropped in this state"),
    Control("C-3", "D-14",
            "a 2.00 g captive mass is released inside the closed article, "
            "against a 0.10 g mass limit",
            2.00, "g",
            "D-14 must show a mass change >= 1.9 g on the article-plus-parts "
            "weighing, and an audible impact on rotation",
            "the loose-part check cannot find a detached part, which is the "
            "one failure a functional check alone never sees",
            "inert mass, no sharp edges, article closed"),
    Control("C-5", "D-19",
            "a reference sharp artifact -- a new steel scribe point -- is "
            "presented to the tester and moves the sensing head a measured "
            "0.012 in, against the 0.005 in limit",
            0.012, "in",
            "D-19 must indicate SHARP on the reference artifact before any "
            "article is screened",
            "the point tester does not indicate on a known sharp point, so "
            "every not-sharp reading it has produced is meaningless",
            "a bench artifact, handled with the article closed and no cell "
            "present; nothing is dropped or powered"),
    Control("C-6", "D-20",
            "a reference blade -- a new utility knife blade -- is run against "
            "the mandrel under the same 1.35 lbf, cutting a measured 1.20 in "
            "of tape against a 0.5 in limit",
            1.20, "in",
            "D-20 must cut at least 1.0 in on the reference blade before any "
            "article is screened",
            "the edge tester cannot cut on a known sharp edge, so every "
            "not-sharp reading it has produced is meaningless",
            "a bench artifact, blade handled in a holder; no article, no cell"),
    Control("C-4", "D-17",
            "one fastener is set to 0.10 N.m install torque instead of 0.35, "
            "giving a residual breakaway below the 0.25 N.m floor",
            0.10, "N.m",
            "D-17 must read a breakaway torque <= 0.15 N.m",
            "fastener retention is not being measured and the torque check "
            "must be replaced",
            "no live cell; the article is not dropped in this state"),
)


# --- staging ----------------------------------------------------------------

STAGES = (
    ("0", "bench", "inert", "record as-built state, every baseline in CHECKS, "
     "and photographs", "all baselines recorded and within their build spec",
     "n/a"),
    ("1", "enclosure with dummy mass, inert or non-functional internals",
     "inert dummy of matched mass, centre of mass, envelope, mounting "
     "interface and mount stiffness",
     "full drop family, then the rough-play family",
     "BOTH articles complete the full sequence with every check inside its "
     "threshold, AND every control in CONTROLS has been shown to go red on "
     "the control article",
     "any failure fails the stage; see the restart rule"),
    ("2", "representative assembled unit in the intended material and process",
     "inert dummy, same equivalence as stage 1",
     "the same sequence, on articles built to a recorded process",
     "as stage 1; this is the qualifying stage",
     "any failure fails the stage; see the restart rule"),
    ("3", "live-cell trial", "NOT PROPOSED", "NOT PROPOSED",
     "not scheduled and not implied by this document",
     "would require a separate safety review by PM and Michael"),
)

DUMMY_EQUIVALENCE = (
    ("mass", "+/- 2 g of the cell it replaces"),
    ("centre of mass", "+/- 2 mm in each axis"),
    ("envelope", "+/- 0.5 mm on each dimension"),
    ("mounting interface", "identical features, same fasteners, same torque"),
    ("mount stiffness", "within 20% of the cell's, measured as deflection "
     "under a 5.0 N transverse load"),
)

RESTART_RULE = (
    "A repair, a redesign or any change to the article, the material or the "
    "process restarts the ENTIRE affected cumulative family, on FRESH "
    "articles, for BOTH articles -- not the failed orientation alone. The "
    "drop family and the rough-play family are separate families for this "
    "purpose; a change that can only affect one restarts only that one, and "
    "the reason is recorded. Every control that covers a check in the "
    "restarted family is rerun before the articles are exposed."
)

QUARANTINE_RULE = (
    "A failed article is photographed as found, bagged, labelled with its "
    "article id, the step it failed and the date, and retained until the "
    "package is accepted. It is never returned to a sequence, never used for "
    "a later stage, and never repaired for reuse as a test article. Its data "
    "stays in the record: a failure is not deleted by a later pass."
)

DISTURB_RULE = (
    "A check marked DISTURBS changes the article -- opening it, releasing a "
    "fastener or unmating a connector. Those run at stage 0, at every third "
    "drop, and at the end of a family, never in the middle of a cumulative "
    "sequence. Non-disturbing checks run after every event. An article that "
    "has been opened is reassembled to the recorded install torque before the "
    "sequence continues, and the reassembly is recorded as an event."
)


# --- generation -------------------------------------------------------------

def block(name: str, lines: list[str]) -> str:
    return (f"<!-- BEGIN GENERATED: {name} -->\n" + "\n".join(lines) +
            f"\n<!-- END GENERATED: {name} -->")


def gen_drops() -> str:
    lines = [f"**Datum:** {AXES}.", "",
             "| # | Orientation | What lands |", "|---|---|---|"]
    for d in drop_sequence():
        lines.append(f"| {d.step} | `{d.orientation}` | {d.why} |")
    lines += ["",
              f"**{len(drop_sequence())} drops per article, cumulative, in this "
              f"order.** {DROP['screen_rule']}", "",
              f"- height **{DROP['height_m']:.2f} m** "
              f"(+{DROP['height_tolerance_m'][0]*1000:.0f} / "
              f"{DROP['height_tolerance_m'][1]*1000:.0f} mm), datum: "
              f"{DROP['height_datum']}",
              f"- surface: {DROP['surface']}",
              f"- release: {DROP['release']}",
              f"- attitude within **±{DROP['attitude_tolerance_deg']:.0f}°** of "
              f"the nominal orientation at release",
              f"- the article is left untouched for "
              f"{DROP['settle_s']:.0f} s after impact, then checked"]
    return block("rugged_drops", lines)


def gen_checks() -> str:
    lines = ["| ID | Measures | Instrument | Range · resolution · accuracy | "
             "Calibration | Baseline | Threshold | Disturbs? |",
             "|---|---|---|---|---|---|---|---|"]
    for c in CHECKS:
        lines.append(
            f"| **{c.id}** | {c.what} | {c.instrument} | {c.range_} · "
            f"{c.resolution} · {c.accuracy} | {c.calibration} | {c.baseline} | "
            f"**{c.threshold}** | {'**yes**' if c.disturbs else 'no'} |")
    lines += ["", DISTURB_RULE]
    return block("rugged_checks", lines)


def gen_controls() -> str:
    lines = ["| Control | Targets | Injected defect | Margin | Must read | "
             "If it does not go red |", "|---|---|---|---|---|---|"]
    for c in CONTROLS:
        t = CHECK_BY_ID[c.targets]
        lines.append(
            f"| **{c.id}** | {c.targets} | {c.defect} | "
            f"**{t.margin(c.magnitude):.1f}×** past the {t.limit} {t.unit} "
            f"limit | "
            f"{c.detected_by} | {c.if_it_passes} |")
    lines += ["",
              "Each control runs **before** the articles it protects are "
              "exposed, on a control article that never produces a qualifying "
              "result. Safety: " +
              "; ".join(f"{c.id} — {c.safety}" for c in CONTROLS) + "."]
    return block("rugged_controls", lines)


def gen_stages() -> str:
    lines = ["| Stage | Article | Cell | What runs | Exit gate | On failure |",
             "|---|---|---|---|---|---|"]
    for s in STAGES:
        lines.append("| " + " | ".join(s) + " |")
    lines += ["", "**Dummy equivalence** — an inert dummy matched on mass "
              "alone is not equivalent:", "",
              "| Property | Tolerance |", "|---|---|"]
    for k, v in DUMMY_EQUIVALENCE:
        lines.append(f"| {k} | {v} |")
    lines += ["", f"**Restart.** {RESTART_RULE}", "",
              f"**Quarantine.** {QUARANTINE_RULE}"]
    return block("rugged_stages", lines)


def gen_shake() -> str:
    lines = [
        f"**Shake.** {SHAKE['displacement_definition']}, "
        f"**{SHAKE['displacement_mm']:.0f} ± {SHAKE['displacement_tolerance_mm']:.0f} mm**, "
        f"at **{SHAKE['frequency_hz']:.1f} ± {SHAKE['frequency_tolerance_hz']:.1f} Hz**.",
        "",
        f"- displacement measured {SHAKE['measured_how']}",
        f"- frequency verified by {SHAKE['frequency_verified_how']}",
        f"- grip: {SHAKE['grip']}",
        f"- **{SHAKE['bouts_per_axis']} bouts of {SHAKE['bout_s']:.0f} s** with "
        f"{SHAKE['rest_s']:.0f} s rest, per axis, three axes "
        f"({', '.join(SHAKE['axes'])}) — {SHAKE['per_axis_s']:.0f} s per axis in total",
        f"- {SHAKE['feasibility']}",
        "",
        f"**Tumble.** {TUMBLE['count']} tumbles in a "
        f"{TUMBLE['box_internal_mm'][0]}×{TUMBLE['box_internal_mm'][1]}×"
        f"{TUMBLE['box_internal_mm'][2]} mm internal box, {TUMBLE['box_wall']}.",
        "",
        f"- one tumble = {TUMBLE['one_tumble']}",
        f"- fall height **{TUMBLE['fall_height_m']:.2f} m**, "
        f"{TUMBLE['fall_height_basis']}",
        f"- {TUMBLE['rate_s_per_tumble']:.0f} s per tumble; {TUMBLE['loading']}",
        f"- completion: {TUMBLE['completion']}",
    ]
    return block("rugged_roughplay", lines)


def gen_sharp() -> str:
    lines = [
        f"**Adopted sources**, retrieved {sharp.RETRIEVED}: "
        + "; ".join(f"[{v['cite']}]({v['url']}) — {v['title']}"
                    for v in sharp.SOURCES.values()) + ".",
        "",
        f"> {sharp.DISCLAIMER}",
        "",
        f"**{sharp.RETRY_RECORD}**",
        "",
        f"**Provenance of every value below:** {sharp.RETRIEVAL}. No field is "
        f"marked verified against the primary document, and the edition banner "
        f"(\"current through\") could not be read. See CS-1..CS-5.",
        "",
        "### Accessibility basis", "",
        "| Field | Value | Cited as |", "|---|---|---|",
    ]
    for f in sharp.ACCESSIBILITY:
        lines.append(f"| {f.name} | **{f.rendered()}** | {f.cite} |")
    lines += ["", "### Sharp-point tester and criterion", "",
              "| Field | Value | Cited as |", "|---|---|---|"]
    for f in sharp.POINT:
        lines.append(f"| {f.name} | **{f.rendered()}** | {f.cite} |")
    lines += ["", "### Sharp-edge tester and criterion", "",
              "| Field | Value | Cited as |", "|---|---|---|"]
    for f in sharp.EDGE:
        lines.append(f"| {f.name} | **{f.rendered()}** | {f.cite} |")
    lines += ["", "### Not recovered, and therefore not stated", "",
              "| # | Missing | Consequence |", "|---|---|---|"]
    for cid, what, why in sharp.OPEN:
        lines.append(f"| **{cid}** | {what} | {why} |")
    lines += ["", "### Probe B geometry (CS-1 — dimensioned, not verified)", "",
              "| Dim | Value | Cited as |", "|---|---|---|"]
    for f in sharp.PROBE_B:
        lines.append(f"| {f.name} | **{f.rendered()}** | {f.cite} |")
    lines += ["",
              "### Use-and-abuse conditioning for the seven-year band", "",
              "| Condition | Value | Cited as |", "|---|---|---|"]
    for f in sharp.USE_AND_ABUSE:
        lines.append(f"| {f.name} | {f.rendered()} | {f.cite} |")
    lines += ["", "### Crosswalk — our method against those conditions", "",
              "Every difference is a gap, stated as one. Being harsher in places "
              "is not equivalence.", "",
              "| Item | Our internal method | The referenced condition | Gap |",
              "|---|---|---|---|"]
    for item, ours, theirs, gap in sharp.CROSSWALK:
        lines.append(f"| {item} | {ours} | {theirs} | {gap} |")
    lines += ["",
              "**Evaluation is deterministic**, in `hardware/rugged/sharp.py`: "
              "`point_run_conforms` and `edge_run_conforms` reject a run whose "
              "tester is out of specification — a non-conforming run yields no "
              "verdict rather than a pass — and `point_is_sharp` / "
              "`edge_is_sharp` then apply the criterion above. R-3 is no longer "
              "a judgement call.",
              "",
              "**What the screen can do today:** nothing physical. The testers "
              "are not owned and no purchase is approved (RG-7), and CS-1 and "
              "CS-2 must close before a conforming probe or consumable can even "
              "be specified."]
    return block("rugged_sharp", lines)


GENERATORS = {
    "rugged_sharp": gen_sharp,
    "rugged_drops": gen_drops,
    "rugged_checks": gen_checks,
    "rugged_controls": gen_controls,
    "rugged_stages": gen_stages,
    "rugged_roughplay": gen_shake,
}


def render(text: str) -> str:
    for name, fn in GENERATORS.items():
        pat = re.compile(
            rf"<!-- BEGIN GENERATED: {name} -->.*?<!-- END GENERATED: {name} -->",
            re.S)
        if not pat.search(text):
            raise SystemExit(f"{SPEC.name}: no generated block for {name}")
        text = pat.sub(lambda _m, f=fn: f().replace("\\", "\\\\"), text, count=1)
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    current = SPEC.read_text()
    new = render(current)
    if args.check:
        if new != current:
            print("protocol.py: spec/hw/ruggedization.md is stale", file=sys.stderr)
            return 1
        print("rugged protocol tables up to date")
        return 0
    SPEC.write_text(new)
    print("regenerated rugged protocol tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
