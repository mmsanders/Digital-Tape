#!/usr/bin/env python3
"""Audit a sustained-write record, deriving every figure from primitives.

This is the half of the measurement path that does not trust anything. It reads
a record written by `measure_sustained_write.py` and recomputes each reported
number from the per-window byte counts and monotonic timestamps. A stored
summary field is never used as an input -- only ever compared against what the
primitives say, and a disagreement is an error, not a note.

That distinction is the whole point. P1-R17-V-A02 found the previous analyser
printing a stored mean it had not checked: changing `38.79` to `999.0` in a raw
file printed `999.00` and still exited 0. Nothing here can do that.

Two schemas exist and the difference is stated, never blurred:

  schema 2  primitives retained -- requested/returned bytes, monotonic start and
            end per window, fsync outcome, final file size, and capacity/free/
            used measured before fill, after fill and after the run. A schema-2
            record can be fully audited, which is what WP-05 A-2 needs.

  schema 1  LEGACY. Rounded MB/s per window and summary fields, nothing else.
            The five files Michael submitted on 16 September 2026 are schema 1
            and are immutable -- they are not rewritten, upgraded or migrated.
            Their arithmetic is checkable and was independently reproduced
            (P1-R17-V). Their physical claims are not: a short write, a wrong
            byte count or an unfilled card cannot be detected after the fact.
            So a schema-1 record audits as LEGACY and is reported as incomplete
            WP-05 A-2 evidence however clean its arithmetic is.

P1-R21-V01 rejected the previous head for the other half of that distrust: the
top level was closed but the nested objects were not, and the primitive types
were not enforced. Thirteen malformed records were accepted -- a closing flush
running backwards, a removed `final_fsync.error`, unknown members inside
`final_fsync`, `fill` and `space_after_measurement`, Boolean sequence and window
identities passing as their integer equivalents, integral floats passing for
byte and capacity counts, and declared `window_mb`/criterion metadata nobody
checked -- and a string timestamp ended the audit in a traceback rather than a
report. So: every nested object is closed, every byte, count and identity field
must be an exact integer, every timestamp must be finite, the closing flush must
run forwards inside the measured span, and the declared metadata is checked
against the retained primitives and against this module's own restated
criterion. Types are settled before the first comparison, because a malformed
record must leave with a problem report the auditor owns.

    python3 audit_sustained_write.py FILE [FILE...]      exit 1 on any problem
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

BYTES_PER_MB = 1_000_000
# Restated here, not imported from the tool: an auditor that reads its
# criterion out of the thing it audits checks nothing. A C-60 is
# 60 x 60 x 44100 x 4 = 635,040,000 B, which over 30 s is 21.168 MB/s, declared
# 21.2. A C-90 is 952,560,000 B, 31.752 MB/s, declared 31.75 and reported only
# -- C-90 is not open (ADR-018). The bar is 10% over the C-60 requirement.
REQUIRED_MB_S = 21.2
REQUIRED_C90_MB_S = 31.75
BAR_MB_S = 23.3
CRITERION_EPS = 1e-9     # a declared criterion must BE the method's, not near it

# Tolerances. Each is a rounding or timer-resolution allowance, not a fudge.
TIME_EPS_S = 1e-6        # duration vs (t_end - t_start): float representation
ELAPSED_EPS_S = 0.05     # elapsed vs (t_last - t_first): the final fsync
ROUND_EPS = 0.006        # a value stored to 2 dp vs one derived at full precision
FILL_EPS = 0.02          # measured occupancy vs the requested fill fraction


@dataclass
class Audit:
    path: Path
    schema: int
    legacy: bool
    rates: list[float] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    derived: dict = field(default_factory=dict)
    # The parse/compute boundary, made explicit. `_audit_shapes` sets this only
    # when every type in the record has been settled. Each function that
    # compares, sums or divides asserts it first, so "validated" is a property
    # of the record in hand rather than of the order someone remembered to
    # write the calls in.
    shapes_validated: bool = False

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def verdict(self) -> str:
        return "PASS" if self.derived.get("worst", 0.0) >= BAR_MB_S else "FAIL"


def _trace_digest(calls: list[dict]) -> str:
    """The same canonical binding the tool computes, recomputed here."""
    h = hashlib.sha256()
    for c in calls:
        h.update(f"{c['seq']}|{c['window']}|{c['offset_bytes']}|"
                 f"{c['requested_bytes']}|{c['returned_bytes']}\n".encode())
    return h.hexdigest()


def sliding_pair_rates(rates: list[float], window_bytes: list[int],
                       durations: list[float]) -> list[float]:
    """Effective rate over EVERY adjacent pair (i, i+1).

    P1-R17-V-A03: the previous implementation used fixed non-overlapping pairs
    (0,1), (2,3)... and called them "any adjacent pair", which they are not --
    it omits (1,2), (3,4) and so on, and those can be lower. For the onn control
    the fixed-pair minimum 18.00776 MB/s becomes 17.76235 over all adjacent
    pairs. This iterates every one of them.

    Total bytes over total time, so it is insensitive to where a window
    boundary falls. It is a descriptive statistic, NOT an A-2 criterion: A-2 is
    judged on the worst single window.
    """
    out = []
    for i in range(len(rates) - 1):
        b = window_bytes[i] + window_bytes[i + 1]
        t = durations[i] + durations[i + 1]
        out.append((b / BYTES_PER_MB) / t if t > 0 else float("inf"))
    return out


def fixed_phase0_pair_rates(rates: list[float], window_bytes: list[int],
                            durations: list[float]) -> list[float]:
    """The schema-1 statistic, kept only so the old numbers stay reproducible.

    Retained under its true name. It is not used for any claim.
    """
    out = []
    for i in range(0, len(rates) - 1, 2):
        b = window_bytes[i] + window_bytes[i + 1]
        t = durations[i] + durations[i + 1]
        out.append((b / BYTES_PER_MB) / t if t > 0 else float("inf"))
    return out


def _close(a: float, b: float, eps: float) -> bool:
    return a is not None and b is not None and math.isclose(a, b, abs_tol=eps)


# Schema 2 is a CLOSED schema. Everything required is listed; anything not
# listed is rejected rather than ignored, because P1-R19-V02 found the opposite
# arrangement accepting thirteen mutations that removed or corrupted the very
# primitives the record exists to carry.

S2_REQUIRED = {
    "schema_version", "target_kind", "measurement_path",
    "measurement_file_retained", "transfer_mb", "window_mb", "bytes_per_mb",
    "requested_bytes_total", "returned_bytes_total", "expected_final_size_bytes",
    "final_size_bytes", "t_first_monotonic_s", "t_last_monotonic_s", "elapsed_s",
    "final_fsync", "windows", "write_trace", "write_trace_sha256",
    "required_mb_s", "required_c90_mb_s", "bar_mb_s", "fill",
    "space_after_measurement", "sku", "revision", "cid", "sample", "reader",
    "measured_at", "host",
}
S2_WINDOW_REQUIRED = {
    "index", "offset_start_bytes", "offset_end_bytes", "requested_bytes",
    "returned_bytes", "write_calls", "short_writes", "t_start_monotonic_s",
    "t_end_monotonic_s", "duration_s", "fsync_ok", "sync_error",
}
S2_CALL_REQUIRED = {"seq", "window", "offset_bytes", "requested_bytes",
                    "returned_bytes"}
# The nested objects are closed too. P1-R21-V01 found every one of these open:
# removing `final_fsync.error`, adding an unknown member to `final_fsync`, `fill`
# or `space_after_measurement`, all passed. A schema that is closed at the top
# and open one level down is not a closed schema.
S2_FSYNC_REQUIRED = {"attempted", "ok", "error", "t_start_monotonic_s",
                     "t_end_monotonic_s"}
S2_SPACE_REQUIRED = {"applies", "reason", "total_bytes", "free_bytes",
                     "used_bytes", "occupancy"}
S2_FILL_REQUIRED = {"requested_fraction", "performed", "reason", "before",
                    "after", "ballast_bytes", "ballast_path"}

# Fields that must be EXACT integers. An integral-valued float is not one: a
# byte count that arrives as 1.0 has been through an arithmetic path that does
# not preserve byte identity, and the record exists to prove byte identity.
S2_INT_FIELDS = ("transfer_mb", "window_mb", "bytes_per_mb",
                 "requested_bytes_total", "returned_bytes_total",
                 "expected_final_size_bytes", "final_size_bytes")
S2_WINDOW_INT_FIELDS = ("index", "offset_start_bytes", "offset_end_bytes",
                        "requested_bytes", "returned_bytes", "write_calls",
                        "short_writes")
S2_CALL_INT_FIELDS = ("seq", "window", "offset_bytes", "requested_bytes",
                      "returned_bytes")
S2_SPACE_INT_FIELDS = ("total_bytes", "free_bytes", "used_bytes")

# Fields that must be finite real numbers. Monotonic clocks and derived
# durations; NaN and infinity compare in ways that silently satisfy bounds.
S2_FLOAT_FIELDS = ("t_first_monotonic_s", "t_last_monotonic_s", "elapsed_s",
                   "required_mb_s", "required_c90_mb_s", "bar_mb_s")
S2_WINDOW_FLOAT_FIELDS = ("t_start_monotonic_s", "t_end_monotonic_s",
                          "duration_s")
S2_FSYNC_FLOAT_FIELDS = ("t_start_monotonic_s", "t_end_monotonic_s")

# The seven members that bind a record to a physical event. They were required
# to be PRESENT and never required to be STRINGS (P1-R23-V01), so an object, a
# list, a number, a Boolean or null passed in place of the card's part number or
# the time of the run. These are the fields a later qualification would cite; a
# record whose SKU is `null` binds nothing, and a closed schema that does not
# type them is not closing the part that matters most.
S2_IDENTITY_FIELDS = ("sku", "revision", "cid", "sample", "reader",
                      "measured_at", "host")

S2_TARGET_KINDS = {"mounted-filesystem", "raw-device"}
# Schema 2 stores primitives. A summary in the file is not authoritative and is
# not quietly ignored: it is a contradiction and the record is rejected.
S2_FORBIDDEN = {"worst_window_mb_s", "mean_mb_s", "median_mb_s", "p05_mb_s",
                "verdict", "windows_mb_s", "filled_to"}


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _int(v) -> bool:
    """An exact integer. `True` is not 1 and `1.0` is not 1."""
    return isinstance(v, int) and not isinstance(v, bool)


def _want_int(a: "Audit", where: str, name: str, v, *, nonneg: bool = True) -> int:
    """Report and count, rather than raise, on anything that is not an integer."""
    if isinstance(v, bool):
        a.problems.append(
            f"{where}{name} is the boolean {v!r}; a byte, count or identity "
            f"field must be an exact integer, and True is not 1 here")
    elif not isinstance(v, int):
        a.problems.append(
            f"{where}{name} is {type(v).__name__} {v!r}; an exact integer is "
            f"required -- an integral-valued float is not an integer byte, "
            f"count or capacity value")
    elif nonneg and v < 0:
        a.problems.append(f"{where}{name} is negative ({v})")
    else:
        return 0
    return 1


def _want_finite(a: "Audit", where: str, name: str, v) -> int:
    """A finite real number. NaN and infinity satisfy bounds they should not."""
    if not _num(v):
        a.problems.append(
            f"{where}{name} is {type(v).__name__} {v!r}; a finite number is "
            f"required, and a malformed value must be rejected here rather "
            f"than raise when it is first compared")
    elif not math.isfinite(v):
        a.problems.append(f"{where}{name} is {v!r}, which is not finite")
    else:
        return 0
    return 1


def _want_bool(a: "Audit", where: str, name: str, v) -> int:
    if not isinstance(v, bool):
        a.problems.append(f"{where}{name} must be a boolean, not "
                          f"{type(v).__name__} {v!r}")
        return 1
    return 0


def _want_str_or_none(a: "Audit", where: str, name: str, v) -> int:
    if v is not None and not isinstance(v, str):
        a.problems.append(f"{where}{name} must be a string or null, not "
                          f"{type(v).__name__} {v!r}")
        return 1
    return 0


def _closed(a: "Audit", where: str, obj, required: set) -> int:
    """Present, a mapping, and neither missing nor carrying unknown members."""
    if not isinstance(obj, dict):
        a.problems.append(f"{where.rstrip(': ')} is {type(obj).__name__}, not "
                          f"an object")
        return 1
    bad = 0
    for missing in sorted(required - set(obj)):
        a.problems.append(f"{where}missing required field {missing!r}")
        bad += 1
    for unknown in sorted(set(obj) - required):
        a.problems.append(f"{where}unknown field {unknown!r} in a closed schema")
        bad += 1
    return bad


def _audit_space_shape(a: "Audit", where: str, sp) -> int:
    """One capacity object: closed, and typed by its own `applies` branch."""
    bad = _closed(a, where, sp, S2_SPACE_REQUIRED)
    if bad:
        return bad
    if _want_bool(a, where, "applies", sp["applies"]):
        return 1
    bad += _want_int(a, where, "total_bytes", sp["total_bytes"])
    # Another denominator. `total_bytes = 0` was reported as invalid and then
    # divided by anyway, one check later (P1-R23-V01). Reporting a bad value and
    # then using it is worse than not checking it: it produces a traceback from
    # code that had already noticed the problem.
    if _int(sp["total_bytes"]) and sp["total_bytes"] <= 0:
        a.problems.append(
            f"{where}total_bytes is {sp['total_bytes']}; occupancy is derived "
            f"by dividing by it, so it must be positive")
        return bad + 1
    if sp["applies"]:
        # A filesystem: every figure is measured, and `reason` is not needed.
        for name in ("free_bytes", "used_bytes"):
            bad += _want_int(a, where, name, sp[name])
        bad += _want_finite(a, where, "occupancy", sp["occupancy"])
        if sp["reason"] is not None:
            a.problems.append(
                f"{where}applies is true but a reason is given ({sp['reason']!r}); "
                f"a reason explains why accounting does NOT apply")
            bad += 1
    else:
        # A raw device: the rest must be absent, not invented (P1-R18 A item 4).
        for name in ("free_bytes", "used_bytes", "occupancy"):
            if sp[name] is not None:
                a.problems.append(
                    f"{where}{name} is {sp[name]!r}, but filesystem accounting "
                    f"does not apply here -- a figure that cannot be measured "
                    f"must be null, not fabricated")
                bad += 1
        if not (isinstance(sp["reason"], str) and sp["reason"].strip()):
            a.problems.append(f"{where}accounting is inapplicable with no "
                              f"reason given")
            bad += 1
    return bad


def _audit_shapes(rec: dict, a: "Audit") -> int:
    """Nested closure and primitive types, before any value is compared.

    P1-R21-V01 found a malformed `final_fsync.t_start_monotonic_s` terminating
    the audit by traceback. A malformed record must leave with a problem report
    the verifier owns, so every type is settled here -- before the first
    comparison that could raise on it.

    Returns the number of findings, so an unrelated failure elsewhere can never
    suppress or be mistaken for one of these.
    """
    bad = 0
    for name in S2_INT_FIELDS:
        bad += _want_int(a, "", name, rec[name])
    for name in S2_FLOAT_FIELDS:
        bad += _want_finite(a, "", name, rec[name])
    bad += _want_bool(a, "", "measurement_file_retained",
                      rec["measurement_file_retained"])
    if not _int(rec["schema_version"]):
        a.problems.append(f"schema_version is not an integer: "
                          f"{rec['schema_version']!r}")
        bad += 1
    for name in ("target_kind", "measurement_path", "write_trace_sha256"):
        if not isinstance(rec[name], str):
            a.problems.append(f"{name} must be a string, not "
                              f"{type(rec[name]).__name__} {rec[name]!r}")
            bad += 1
        elif not rec[name].strip():
            # An empty path is not a path. The record names the file the run
            # wrote; a blank string names nothing and cannot be reconciled
            # against the device the trace claims to describe.
            a.problems.append(
                f"{name} is empty; it must name the object this run actually "
                f"wrote, and a blank string names nothing")
            bad += 1

    # Identity and provenance. Typed, then required to say something: PM's
    # P1-R24 direction is that a schema-2 acquisition's identity strings must be
    # nonempty after trimming, following WP-05's existing identity/result
    # binding. An empty marker is not a weaker binding, it is no binding -- it
    # names no card, no sample, no reader and no moment.
    for name in S2_IDENTITY_FIELDS:
        v = rec[name]
        if not isinstance(v, str):
            a.problems.append(
                f"{name} must be a string, not {type(v).__name__} {v!r}; this "
                f"field binds the record to a physical card, sample, reader, "
                f"time or host and cannot be an arbitrary value")
            bad += 1
        elif not v.strip():
            a.problems.append(
                f"{name} is empty; an empty identity marker binds this record "
                f"to nothing, and a later qualification would cite it")
            bad += 1
        elif name == "measured_at":
            # The other identity fields are free text an auditor cannot check:
            # nothing here can know whether a SKU string names a real part.
            # `measured_at` is different, because it claims a *format* as well
            # as a value, and a run that cannot say when it happened cannot be
            # placed against a card's history, a firmware revision or another
            # sample. Type plus nonempty let 'bogus' through as a timestamp.
            try:
                datetime.fromisoformat(v)
            except ValueError:
                a.problems.append(
                    f"measured_at {v!r} is not an ISO-8601 timestamp; it binds "
                    f"this record to a moment, and an unparseable marker "
                    f"cannot order this run against any other")
                bad += 1

    # A denominator, checked before anything divides by it. `bytes_per_mb = 0`
    # reached the per-window rate division and raised ZeroDivisionError
    # (P1-R23-V01).
    if _int(rec["bytes_per_mb"]) and rec["bytes_per_mb"] <= 0:
        a.problems.append(
            f"bytes_per_mb is {rec['bytes_per_mb']}; every rate in this record "
            f"is divided by it, so it must be positive")
        bad += 1
    if _int(rec["transfer_mb"]) and rec["transfer_mb"] <= 0:
        a.problems.append(f"transfer_mb is {rec['transfer_mb']}; a run that "
                          f"transfers nothing measures nothing")
        bad += 1

    # --- the closing flush ---------------------------------------------------
    fs_bad = _closed(a, "final_fsync: ", rec["final_fsync"], S2_FSYNC_REQUIRED)
    bad += fs_bad
    if not fs_bad:
        fs = rec["final_fsync"]
        for name in ("attempted", "ok"):
            bad += _want_bool(a, "final_fsync: ", name, fs[name])
        bad += _want_str_or_none(a, "final_fsync: ", "error", fs["error"])
        t_bad = sum(_want_finite(a, "final_fsync: ", name, fs[name])
                    for name in S2_FSYNC_FLOAT_FIELDS)
        bad += t_bad
        if not t_bad and fs["t_end_monotonic_s"] < fs["t_start_monotonic_s"]:
            a.problems.append(
                f"final_fsync ends at {fs['t_end_monotonic_s']}, before it "
                f"starts at {fs['t_start_monotonic_s']} -- a flush interval "
                f"that runs backwards does not establish that the last "
                f"durability event was observed in order")
            bad += 1

    # --- windows and the call trace -----------------------------------------
    if not isinstance(rec["windows"], list):
        a.problems.append("windows is not a list")
        bad += 1
    else:
        for i, w in enumerate(rec["windows"]):
            where = f"window {i}: "
            w_bad = _closed(a, where, w, S2_WINDOW_REQUIRED)
            bad += w_bad
            if w_bad:
                continue
            for name in S2_WINDOW_INT_FIELDS:
                bad += _want_int(a, where, name, w[name])
            for name in S2_WINDOW_FLOAT_FIELDS:
                bad += _want_finite(a, where, name, w[name])
            bad += _want_bool(a, where, "fsync_ok", w["fsync_ok"])
            bad += _want_str_or_none(a, where, "sync_error", w["sync_error"])

    if not isinstance(rec["write_trace"], list):
        a.problems.append("write_trace is not a list")
        bad += 1
    else:
        for i, c in enumerate(rec["write_trace"]):
            where = f"write call {i}: "
            c_bad = _closed(a, where, c, S2_CALL_REQUIRED)
            bad += c_bad
            if c_bad:
                continue
            for name in S2_CALL_INT_FIELDS:
                bad += _want_int(a, where, name, c[name])

    # --- fill and the capacity objects --------------------------------------
    fill_bad = _closed(a, "fill: ", rec["fill"], S2_FILL_REQUIRED)
    bad += fill_bad
    if not fill_bad:
        fill = rec["fill"]
        bad += _want_bool(a, "fill: ", "performed", fill["performed"])
        bad += _want_str_or_none(a, "fill: ", "reason", fill["reason"])
        bad += _want_str_or_none(a, "fill: ", "ballast_path", fill["ballast_path"])
        bad += _want_int(a, "fill: ", "ballast_bytes", fill["ballast_bytes"])
        if fill["requested_fraction"] is not None:
            if _want_finite(a, "fill: ", "requested_fraction",
                            fill["requested_fraction"]):
                bad += 1
            elif not 0.0 < fill["requested_fraction"] <= 1.0:
                a.problems.append(
                    f"fill: requested_fraction {fill['requested_fraction']} is "
                    f"not a fraction in (0, 1]")
                bad += 1
        bad += _audit_space_shape(a, "fill.before: ", fill["before"])
        bad += _audit_space_shape(a, "fill.after: ", fill["after"])

        # A performed fill has to be internally consistent, not merely typed.
        # WP-05 A-2's filled condition is the whole point of this branch: a
        # record that claims it filled the card, while saying it asked for no
        # fraction, moved no ballast or started with no free space, is claiming
        # the condition without the evidence for it. Each of these passed type
        # checking and was silently accepted.
        if fill["performed"] is True:
            if fill["requested_fraction"] is None:
                a.problems.append(
                    "fill: performed is true but requested_fraction is null; a "
                    "fill that happened was asked for at some fraction, and the "
                    "filled condition cannot be checked against nothing")
                bad += 1
            if _int(fill["ballast_bytes"]) and fill["ballast_bytes"] <= 0:
                a.problems.append(
                    f"fill: performed is true but ballast_bytes is "
                    f"{fill['ballast_bytes']}; a fill that moved no bytes did "
                    f"not fill anything")
                bad += 1
            if not isinstance(fill["ballast_path"], str) or not fill["ballast_path"].strip():
                a.problems.append(
                    "fill: performed is true but ballast_path names nothing; "
                    "the ballast the run wrote must be identifiable")
                bad += 1
            before = fill["before"]
            if (isinstance(before, dict) and before.get("applies") is True
                    and _int(before.get("free_bytes"))
                    and before["free_bytes"] <= 0):
                a.problems.append(
                    "fill: performed is true but fill.before.free_bytes is 0; "
                    "there was no space to write ballast into, so the recorded "
                    "fill could not have happened as described")
                bad += 1
    bad += _audit_space_shape(a, "space_after_measurement: ",
                              rec["space_after_measurement"])
    if not bad:
        # The parse/compute boundary. Only a record whose every type and
        # denominator has been settled reaches the code that compares, sums and
        # divides; _require_validated asserts this on the way in.
        a.shapes_validated = True
    return bad


def _require_validated(a: "Audit", who: str) -> None:
    """The boundary assertion between parse and compute.

    If this ever fires, the fix is in the parse stage, never a `try` here. A
    computation that can be reached with an unvalidated record is the defect
    P1-R21-V01 and P1-R23-V01 both found, in three different places.
    """
    if not a.shapes_validated:
        raise AssertionError(
            f"{who} was reached without a validated record; compute must be "
            f"unreachable without the parse stage having settled every type "
            f"and denominator")


def _audit_declared(rec: dict, windows: list, a: "Audit") -> None:
    """The declared metadata, against the retained primitives and the method.

    P1-R21-V01: `window_mb` was accepted while the retained windows contradicted
    it, and the three criterion figures were accepted at any value at all. A
    declared number nobody checks is decoration on a safety record.
    """
    _require_validated(a, "_audit_declared")
    mb_unit = rec["bytes_per_mb"]
    win_mb = rec["window_mb"]
    if win_mb <= 0:
        a.problems.append(f"window_mb {win_mb} is not a positive size")
    else:
        want = win_mb * mb_unit
        for i, w in enumerate(windows):
            req = w["requested_bytes"]
            last = i == len(windows) - 1
            if req > want:
                a.problems.append(
                    f"window {i} requested {req} bytes, more than the declared "
                    f"window_mb ({win_mb} x {mb_unit} = {want})")
            elif not last and req != want:
                a.problems.append(
                    f"window {i} requested {req} bytes, not the declared "
                    f"window_mb ({win_mb} x {mb_unit} = {want}); only the final "
                    f"window may be short")
            elif last and req <= 0:
                a.problems.append(f"window {i} requested {req} bytes")

    for name, want_v in (("required_mb_s", REQUIRED_MB_S),
                         ("required_c90_mb_s", REQUIRED_C90_MB_S),
                         ("bar_mb_s", BAR_MB_S)):
        if not _close(rec[name], want_v, CRITERION_EPS):
            a.problems.append(
                f"declared {name} {rec[name]} is not the method's {want_v}; a "
                f"record that carries its own criterion can otherwise move the "
                f"bar it is judged against")


def audit_schema2(rec: dict, a: Audit) -> None:
    # --- closure: required present, forbidden absent, nothing unknown --------
    keys = set(rec)
    for missing in sorted(S2_REQUIRED - keys):
        a.problems.append(f"missing required field {missing!r}")
    for banned in sorted(S2_FORBIDDEN & keys):
        a.problems.append(
            f"{banned!r} is a stored summary; schema 2 holds primitives and "
            f"derives every figure, so a summary in the file is a contradiction")
    for unknown in sorted(keys - S2_REQUIRED - S2_FORBIDDEN):
        a.problems.append(f"unknown field {unknown!r} in a closed schema")
    if a.problems:
        return            # nothing below can be trusted on an unsound record

    # --- shapes and primitive types, before any value is compared -----------
    # Everything after this line compares, sums and divides. A malformed type
    # reaching those comparisons is how P1-R21-V01 terminated the audit by
    # traceback instead of by a problem report, so types are settled first and
    # a typed record is the only kind that gets further.
    if _audit_shapes(rec, a):
        return

    kind = rec["target_kind"]
    if kind not in S2_TARGET_KINDS:
        a.problems.append(
            f"target_kind {kind!r} is not one of {sorted(S2_TARGET_KINDS)}; an "
            f"invented kind would evade the branch that checks final size")
        return

    mb_unit = rec["bytes_per_mb"]
    if mb_unit != BYTES_PER_MB:
        a.notes.append(f"record declares 1 MB = {mb_unit} bytes")

    windows = rec["windows"]
    if not windows:
        a.problems.append("no windows recorded")
        return

    # --- windows: order, offsets, arithmetic, timing -------------------------
    rates, byts, durs = [], [], []
    prev_end_t = None
    for i, w in enumerate(windows):
        where = f"window {i}"
        # Closure and types are already settled by _audit_shapes; what is left
        # here is what the numbers say.
        if w["index"] != i:
            a.problems.append(
                f"{where}: index {w['index']} is out of order or duplicated")

        want_start = 0 if i == 0 else windows[i - 1].get("offset_end_bytes")
        if w["offset_start_bytes"] != want_start:
            a.problems.append(
                f"{where}: starts at byte {w['offset_start_bytes']}, but the "
                f"previous window ended at {want_start} -- the transfer is not "
                f"contiguous")
        if w["offset_end_bytes"] != w["offset_start_bytes"] + w["returned_bytes"]:
            a.problems.append(
                f"{where}: end offset {w['offset_end_bytes']} does not equal "
                f"start + returned ({w['offset_start_bytes']} + "
                f"{w['returned_bytes']})")
        if w["returned_bytes"] != w["requested_bytes"]:
            a.problems.append(
                f"{where}: returned {w['returned_bytes']} of "
                f"{w['requested_bytes']} requested bytes -- the window was not "
                f"completed")
        if w["short_writes"] != w["write_calls"] - 1:
            a.problems.append(
                f"{where}: short_writes {w['short_writes']} does not equal "
                f"write_calls - 1 ({w['write_calls'] - 1})")
        if w["t_end_monotonic_s"] <= w["t_start_monotonic_s"]:
            a.problems.append(f"{where}: end is not after start")
            continue
        span = w["t_end_monotonic_s"] - w["t_start_monotonic_s"]
        if not _close(w["duration_s"], span, TIME_EPS_S):
            a.problems.append(
                f"{where}: stored duration {w['duration_s']} does not match its "
                f"own timestamps ({span})")
        if prev_end_t is not None and \
                w["t_start_monotonic_s"] < prev_end_t - TIME_EPS_S:
            a.problems.append(
                f"{where}: starts at {w['t_start_monotonic_s']}, before the "
                f"previous window ended ({prev_end_t}) -- the windows are not a "
                f"single ordered run")
        if not w["fsync_ok"]:
            a.problems.append(f"{where}: fsync failed: {w['sync_error']}")
        prev_end_t = w["t_end_monotonic_s"]
        rates.append((w["returned_bytes"] / mb_unit) / span)
        byts.append(w["returned_bytes"])
        durs.append(span)

    # --- the declared metadata, against those same primitives ---------------
    _audit_declared(rec, windows, a)

    # --- the write-call trace: prove it, do not believe it -------------------
    _audit_trace(rec, windows, a)

    if not rates:
        a.problems.append("no usable window primitives")
        return
    a.rates = rates

    # --- totals --------------------------------------------------------------
    summed_req = sum(w["requested_bytes"] for w in windows
                     if _num(w.get("requested_bytes")))
    summed_ret = sum(byts)
    if rec["requested_bytes_total"] != summed_req:
        a.problems.append(
            f"requested_bytes_total {rec['requested_bytes_total']} != the "
            f"{summed_req} its windows request")
    if rec["returned_bytes_total"] != summed_ret:
        a.problems.append(
            f"returned_bytes_total {rec['returned_bytes_total']} != the "
            f"{summed_ret} its windows account for")
    expected = rec["expected_final_size_bytes"]
    if summed_ret != expected:
        a.problems.append(
            f"windows account for {summed_ret} bytes but the run expected "
            f"{expected} -- the transfer is not the size it claims")
    declared = rec["transfer_mb"] * mb_unit
    if expected != declared:
        a.problems.append(
            f"expected_final_size_bytes {expected} != transfer_mb "
            f"({rec['transfer_mb']}) x {mb_unit}")

    # --- final size, by target branch ---------------------------------------
    final = rec["final_size_bytes"]
    if kind == "mounted-filesystem":
        if rec["measurement_file_retained"] is not True:
            a.problems.append(
                "measurement file was deleted, so its final size proves nothing")
        elif not _num(final):
            a.problems.append("no final measurement-file size recorded")
        elif final != expected:
            a.problems.append(
                f"final file size {final} != {expected} bytes written")
    else:   # raw-device
        if rec["measurement_file_retained"] is not False:
            a.problems.append(
                "a raw device has no measurement file to retain; "
                "measurement_file_retained must be false")
        if not _num(final):
            a.problems.append("no device size recorded")
        elif final < expected:
            a.problems.append(
                f"device size {final} is smaller than the {expected} written")

    # --- timing at the top level, and the closing flush ----------------------
    t_first, t_last = rec["t_first_monotonic_s"], rec["t_last_monotonic_s"]
    if not (_num(t_first) and _num(t_last)) or t_last <= t_first:
        a.problems.append("top-level timing is missing or not ordered")
    else:
        span = t_last - t_first
        if not _close(rec["elapsed_s"], span, ELAPSED_EPS_S):
            a.problems.append(
                f"stored elapsed {rec['elapsed_s']} != {span} from its own "
                f"first/last timestamps")
        if sum(durs) > span + ELAPSED_EPS_S:
            a.problems.append(
                f"window durations sum to {sum(durs):.3f} s, more than the "
                f"{span:.3f} s the run took")
        fs = rec["final_fsync"]
        if fs["attempted"] is not True:
            a.problems.append("no closing fsync was attempted, so the run does "
                              "not establish the data reached the device")
        elif fs["ok"] is not True:
            a.problems.append(f"the closing fsync failed: {fs['error']}")
        elif fs["ok"] and fs["error"] is not None:
            a.problems.append(
                f"the closing fsync reports success and an error "
                f"({fs['error']!r}); one of the two is untrue")
        elif not (t_first <= fs["t_start_monotonic_s"]
                  and fs["t_end_monotonic_s"] <= t_last + TIME_EPS_S):
            a.problems.append(
                f"the closing fsync ran at [{fs['t_start_monotonic_s']}, "
                f"{fs['t_end_monotonic_s']}], outside the measured span "
                f"[{t_first}, {t_last}] -- a flush after the clock stops is "
                f"time the record does not account for")

    _audit_space(rec, a)


def _audit_trace(rec: dict, windows: list, a: Audit) -> None:
    """Every write call, in order, reconstructing each window from scratch."""
    _require_validated(a, "_audit_trace")
    trace = rec["write_trace"]
    if not isinstance(trace, list) or not trace:
        a.problems.append("write_trace is missing or empty; a window's byte "
                          "count cannot be proven without its calls")
        return
    # Count only THIS function's findings. Bailing because some unrelated check
    # already failed is how a trace audit silently stops running on exactly the
    # records that need it most.
    mine = 0
    for i, c in enumerate(trace):
        for missing in sorted(S2_CALL_REQUIRED - set(c)):
            a.problems.append(f"write call {i}: missing {missing!r}")
            mine += 1
        for unknown in sorted(set(c) - S2_CALL_REQUIRED):
            a.problems.append(f"write call {i}: unknown field {unknown!r}")
            mine += 1
    if mine:
        return

    if [c["seq"] for c in trace] != list(range(len(trace))):
        a.problems.append(
            "write_trace sequence numbers are not 0..n-1 in order -- a call was "
            "duplicated, reordered or skipped")
        return

    digest = _trace_digest(trace)
    if rec["write_trace_sha256"] != digest:
        a.problems.append(
            f"write_trace_sha256 {rec['write_trace_sha256']!r} does not match "
            f"the trace it claims to bind ({digest!r})")

    cursor = 0
    per_window: dict[int, list] = {}
    for c in trace:
        i = c["seq"]
        if not all(_num(c[f]) for f in ("offset_bytes", "requested_bytes",
                                        "returned_bytes")):
            a.problems.append(f"write call {i}: non-numeric byte counts")
            return
        if c["returned_bytes"] <= 0:
            a.problems.append(f"write call {i}: returned {c['returned_bytes']} "
                              f"bytes; a call that wrote nothing is not progress")
        if c["returned_bytes"] > c["requested_bytes"]:
            a.problems.append(
                f"write call {i}: returned {c['returned_bytes']} bytes, more "
                f"than the {c['requested_bytes']} requested")
        if c["offset_bytes"] != cursor:
            a.problems.append(
                f"write call {i}: starts at offset {c['offset_bytes']}, but the "
                f"preceding calls end at {cursor} -- the continuation did not "
                f"resume where the short write stopped")
            return
        cursor += c["returned_bytes"]
        per_window.setdefault(c["window"], []).append(c)

    if set(per_window) != set(range(len(windows))):
        a.problems.append(
            f"the trace covers windows {sorted(per_window)}, the record has "
            f"{len(windows)}")
        return

    for idx, w in enumerate(windows):
        calls = per_window[idx]
        if not S2_WINDOW_REQUIRED <= set(w):
            continue      # already reported as malformed; do not crash on it
        got = sum(c["returned_bytes"] for c in calls)
        if got != w["returned_bytes"]:
            a.problems.append(
                f"window {idx}: its calls account for {got} bytes, the window "
                f"claims {w['returned_bytes']}")
        if len(calls) != w["write_calls"]:
            a.problems.append(
                f"window {idx}: {len(calls)} calls in the trace, the window "
                f"claims write_calls = {w['write_calls']}")
        if calls[0]["offset_bytes"] != w["offset_start_bytes"]:
            a.problems.append(
                f"window {idx}: its first call is at {calls[0]['offset_bytes']}, "
                f"the window starts at {w['offset_start_bytes']}")
        first_req = calls[0]["requested_bytes"]
        if first_req != w["requested_bytes"]:
            a.problems.append(
                f"window {idx}: its first call asked for {first_req} bytes, the "
                f"window requested {w['requested_bytes']}")

    if cursor != rec["returned_bytes_total"]:
        a.problems.append(
            f"the trace writes {cursor} bytes end to end, the record totals "
            f"{rec['returned_bytes_total']}")


def _audit_space(rec: dict, a: Audit) -> None:
    """Capacity accounting: arithmetic, and before/after consistency."""
    _require_validated(a, "_audit_space")
    def check(label: str, sp) -> bool:
        if not isinstance(sp, dict) or "applies" not in sp:
            a.problems.append(f"{label}: missing capacity accounting")
            return False
        if not sp["applies"]:
            if rec["target_kind"] != "raw-device":
                a.problems.append(
                    f"{label}: declares filesystem accounting inapplicable on a "
                    f"{rec['target_kind']} target")
            if not sp.get("reason"):
                a.problems.append(f"{label}: inapplicable, with no reason given")
            return False
        total, free, used = sp.get("total_bytes"), sp.get("free_bytes"), \
            sp.get("used_bytes")
        if not all(_num(v) for v in (total, free, used)):
            a.problems.append(f"{label}: total/free/used are not all numbers")
            return False
        if total <= 0 or free < 0 or used < 0:
            a.problems.append(f"{label}: negative or zero capacity figures")
        if used + free > total:
            a.problems.append(
                f"{label}: used {used} + free {free} exceeds total {total}")
        if total <= 0:
            # Defence in depth: the shape pass rejects this before we get here,
            # and if it ever stops doing so the failure must still be a report.
            a.problems.append(f"{label}: total {total} cannot be a denominator")
            return False
        occ = sp.get("occupancy")
        if not _num(occ) or not _close(occ, used / total, 1e-6):
            a.problems.append(
                f"{label}: occupancy {occ} does not equal used/total "
                f"({used / total if total else 'n/a'})")
        return True

    fill = rec["fill"]
    if not isinstance(fill, dict) or "performed" not in fill:
        a.problems.append("fill record is missing")
        return
    before_ok = check("fill.before", fill.get("before"))
    after_ok = check("fill.after", fill.get("after"))
    end_ok = check("space_after_measurement", rec["space_after_measurement"])

    if fill.get("performed"):
        after = fill.get("after") or {}
        want = fill.get("requested_fraction")
        occ = after.get("occupancy")
        if not after_ok or occ is None:
            a.problems.append(
                "fill was performed but no post-fill occupancy was measured")
        elif want is not None and occ < want - FILL_EPS:
            a.problems.append(
                f"post-fill occupancy {occ:.3f} is below the requested "
                f"{want:.3f} -- the card was not filled as claimed")
        else:
            a.derived["fill_occupancy"] = occ
        if before_ok and after_ok:
            if after["used_bytes"] < (fill.get("before") or {})["used_bytes"]:
                a.problems.append(
                    "the fill left less used space than it started with")
            ballast = fill.get("ballast_bytes")
            if _num(ballast) and ballast > 0:
                grew = after["used_bytes"] - fill["before"]["used_bytes"]
                if grew < ballast * 0.9:
                    a.problems.append(
                        f"the fill claims {ballast} bytes of ballast but used "
                        f"space grew by only {grew}")
    elif fill.get("requested_fraction") is not None and not fill.get("reason"):
        a.problems.append("a fill fraction was requested but no fill was "
                          "performed and no reason recorded")

    if after_ok and end_ok:
        end = rec["space_after_measurement"]
        if end["used_bytes"] < (fill.get("after") or {})["used_bytes"] - 1:
            a.problems.append(
                "used space shrank across the measurement, but the run only "
                "writes -- something was deleted, and the record does not say "
                "what")


def audit_schema1(rec: dict, a: Audit) -> None:
    """Legacy: rate vector only. Check what is checkable, claim nothing more."""
    rates = rec.get("windows_mb_s")
    if not rates:
        a.problems.append("no window rates recorded")
        return
    a.rates = [float(r) for r in rates]
    a.notes.append(
        "schema 1: no per-window byte counts, no timestamps, no final size and "
        "no measured occupancy. Arithmetic is checkable; the physical run is "
        "not. NOT complete WP-05 A-2 evidence.")

    # Stored summaries are compared, never trusted (P1-R17-V-A02).
    worst = min(a.rates)
    if rec.get("worst_window_mb_s") is not None and \
            not _close(rec["worst_window_mb_s"], worst, ROUND_EPS):
        a.problems.append(
            f"stored worst_window_mb_s {rec['worst_window_mb_s']} != {worst:.5f} "
            f"from the recorded vector")

    transfer, elapsed = rec.get("transfer_mb"), rec.get("elapsed_s")
    if transfer is not None and elapsed:
        derived_mean = (transfer * (1 << 20)) / BYTES_PER_MB / elapsed
        a.derived["mean_from_elapsed"] = derived_mean
        stored_mean = rec.get("mean_mb_s")
        if stored_mean is not None and not _close(stored_mean, derived_mean, ROUND_EPS):
            a.problems.append(
                f"stored mean_mb_s {stored_mean} != {derived_mean:.5f} derived "
                f"from transfer_mb and elapsed_s")

    stored_median = rec.get("median_mb_s")
    if stored_median is not None and not _close(stored_median,
                                                statistics.median(a.rates), ROUND_EPS):
        a.problems.append(
            f"stored median_mb_s {stored_median} != "
            f"{statistics.median(a.rates):.5f} from the recorded vector")

    stored_verdict = rec.get("verdict")
    want = "PASS" if worst >= rec.get("bar_mb_s", BAR_MB_S) else "FAIL"
    if stored_verdict is not None and stored_verdict != want:
        a.problems.append(
            f"stored verdict {stored_verdict} != {want} recomputed from the vector")


def audit(path: Path) -> Audit:
    try:
        rec = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        a = Audit(path=Path(path), schema=0, legacy=False)
        a.problems.append(f"unreadable: {exc}")
        return a

    # P1-R23-V01: everything below indexes and membership-tests `rec`. A JSON
    # document whose top-level value is a list, a string or a number is valid
    # JSON and is not a record, and reaching `"x" in rec` with an int raises
    # rather than reports. The type of the thing being audited is the first
    # question, not an assumed one.
    if not isinstance(rec, dict):
        a = Audit(path=Path(path), schema=0, legacy=False)
        a.problems.append(
            f"the top-level JSON value is {type(rec).__name__}, not an object; "
            f"a record is a mapping of fields and nothing else can be audited "
            f"as one")
        return a

    if "schema_version" not in rec:
        # Absence means schema 1 -- but only for a record that actually looks
        # like one. A record carrying schema-2 structures without declaring its
        # version is not legacy evidence, it is an unversioned record.
        if {"windows", "write_trace", "final_fsync"} & set(rec):
            a = Audit(path=Path(path), schema=0, legacy=False)
            a.problems.append(
                "missing required field 'schema_version' on a record that "
                "carries schema-2 structures")
            return a
    # P1-R23-V01, two defects in one line. `int(...)` COERCED the declared
    # version before anything had checked its type, so `"bogus"` raised
    # ValueError instead of being reported; and the dispatch below read
    # `schema >= 2`, so a record declaring schema 3 was audited against the
    # schema-2 contract as though the two were the same thing. This method
    # documents exactly schemas 1 and 2. A version it does not document is not
    # a version it can audit, and guessing which contract the author meant is
    # the opposite of a closed schema.
    declared = rec.get("schema_version", 1)
    if "schema_version" in rec and not _int(declared):
        a = Audit(path=Path(path), schema=0, legacy=False)
        a.problems.append(
            f"schema_version is {type(declared).__name__} {declared!r}, not an "
            f"integer; the declared version selects the contract the record is "
            f"judged against and is not coerced into one")
        return a

    schema = declared
    a = Audit(path=Path(path), schema=schema, legacy=schema < 2)
    if schema == 2:
        audit_schema2(rec, a)
    elif schema == 1:
        audit_schema1(rec, a)
    else:
        a.problems.append(
            f"schema_version {schema} is not a version this method defines; it "
            f"documents exactly 1 (legacy) and 2, and auditing an undefined "
            f"version against the schema-2 contract would assert a contract "
            f"nobody wrote")
        return a

    if a.rates:
        if schema >= 2:
            byts = [w["returned_bytes"] for w in rec["windows"]]
            durs = [w["t_end_monotonic_s"] - w["t_start_monotonic_s"]
                    for w in rec["windows"]]
        else:
            # Schema 1 called `window_mb << 20` bytes a "64 MB window" and then
            # divided by 10^6 to get MB/s -- so its windows are 64 MiB and its
            # MB is 10^6. Reconstruct on ITS convention, or the pair rates come
            # out 4.6% low and stop matching the independently reproduced
            # values. Schema 2 uses 10^6 throughout and does not have this.
            win_b = rec.get("window_mb", 64) * (1 << 20)
            byts = [win_b] * len(a.rates)
            durs = [(win_b / BYTES_PER_MB) / r for r in a.rates]
            a.notes.append(
                f"schema 1 window is {win_b} bytes (MiB-sized) while its rates "
                f"are in 10^6 MB/s; schema 2 uses 10^6 for both")
        a.derived |= {
            "windows": len(a.rates),
            "worst": min(a.rates),
            "best": max(a.rates),
            "median": statistics.median(a.rates),
            "mean_of_windows": statistics.fmean(a.rates),
            "headroom_c60": min(a.rates) / REQUIRED_MB_S,
            "headroom_bar": min(a.rates) / BAR_MB_S,
            "pair_min_sliding": min(sliding_pair_rates(a.rates, byts, durs)),
            "pair_min_fixed_phase0": min(fixed_phase0_pair_rates(a.rates, byts, durs)),
            "short_writes": sum(w.get("short_writes", 0)
                                for w in rec["windows"]) if schema >= 2 else None,
            "write_calls": len(rec.get("write_trace", [])) if schema >= 2 else None,
        }
    return a


def report(a: Audit) -> None:
    tag = f"schema {a.schema}" + (" LEGACY" if a.legacy else "")
    print(f"{a.path.name}  [{tag}]")
    if a.derived:
        d = a.derived
        print(f"  windows {d['windows']}  worst {d['worst']:.5f}  "
              f"median {d['median']:.5f}  best {d['best']:.5f}  MB/s")
        print(f"  headroom  {d['headroom_c60']:.3f}x C-60 requirement, "
              f"{d['headroom_bar']:.3f}x the {BAR_MB_S} MB/s screen")
        print(f"  adjacent-pair minimum (every pair) {d['pair_min_sliding']:.5f}"
              f"   [fixed phase-0 pairs: {d['pair_min_fixed_phase0']:.5f}]")
        if d.get("fill_occupancy") is not None:
            print(f"  measured occupancy after fill  {d['fill_occupancy']:.3f}")
        if d.get("short_writes"):
            print(f"  short writes completed by looping: {d['short_writes']}")
        print(f"  screen  {a.verdict}  (derived, not read from the file)")
    for n in a.notes:
        print(f"  note: {n}")
    for p in a.problems:
        print(f"  FAIL: {p}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args(argv)

    bad = 0
    for i, f in enumerate(sorted(args.files)):
        if i:
            print()
        a = audit(f)
        report(a)
        bad += not a.ok
    print()
    if bad:
        print(f"{bad} of {len(args.files)} record(s) failed the audit")
        return 1
    print(f"all {len(args.files)} record(s) internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
