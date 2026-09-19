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

    python3 audit_sustained_write.py FILE [FILE...]      exit 1 on any problem
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

BYTES_PER_MB = 1_000_000
REQUIRED_MB_S = 21.2
BAR_MB_S = 23.3

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

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def verdict(self) -> str:
        return "PASS" if self.derived.get("worst", 0.0) >= BAR_MB_S else "FAIL"


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


def audit_schema2(rec: dict, a: Audit) -> None:
    windows = rec.get("windows")
    if not windows:
        a.problems.append("no windows recorded")
        return

    mb_unit = rec.get("bytes_per_mb", BYTES_PER_MB)
    if mb_unit != BYTES_PER_MB:
        a.notes.append(f"record declares 1 MB = {mb_unit} bytes")

    rates, byts, durs = [], [], []
    prev_end = None
    for i, w in enumerate(windows):
        where = f"window {w.get('index', i)}"
        req, got = w.get("requested_bytes"), w.get("returned_bytes")
        t0, t1 = w.get("t_start_monotonic_s"), w.get("t_end_monotonic_s")
        dur = w.get("duration_s")

        if req is None or got is None:
            a.problems.append(f"{where}: missing requested/returned byte counts")
            continue
        if got != req:
            a.problems.append(
                f"{where}: returned {got} of {req} requested bytes -- a short "
                f"write was not completed, so its rate is not a full window")
        if t0 is None or t1 is None or dur is None:
            a.problems.append(f"{where}: missing monotonic timestamps or duration")
            continue
        if t1 <= t0:
            a.problems.append(f"{where}: end {t1} is not after start {t0}")
            continue
        if not _close(dur, t1 - t0, TIME_EPS_S):
            a.problems.append(
                f"{where}: stored duration {dur} does not match its own "
                f"timestamps ({t1 - t0})")
        if prev_end is not None and t0 < prev_end - TIME_EPS_S:
            a.problems.append(
                f"{where}: starts at {t0}, before the previous window ended "
                f"({prev_end}) -- the windows are not a single ordered run")
        if not w.get("fsync_ok", True):
            a.problems.append(f"{where}: fsync failed: {w.get('sync_error')}")
        prev_end = t1
        rates.append((got / mb_unit) / (t1 - t0))
        byts.append(got)
        durs.append(t1 - t0)

    if not rates:
        a.problems.append("no usable window primitives")
        return
    a.rates = rates

    # Byte accounting, end to end.
    summed = sum(byts)
    if rec.get("returned_bytes_total") not in (None, summed):
        a.problems.append(
            f"returned_bytes_total {rec['returned_bytes_total']} != the "
            f"{summed} bytes its own windows account for")
    expected = rec.get("expected_final_size_bytes")
    if expected is not None and summed != expected:
        a.problems.append(
            f"windows account for {summed} bytes but the run expected "
            f"{expected} -- the transfer is not the size it claims")

    # Final size. A deleted measurement file cannot be checked, and that is a
    # gap in the evidence rather than a clean run.
    final = rec.get("final_size_bytes")
    if rec.get("target_kind") == "mounted-filesystem":
        if not rec.get("measurement_file_retained", False):
            a.problems.append(
                "measurement file was deleted, so its final size proves nothing")
        elif final is None:
            a.problems.append("no final measurement-file size recorded")
        elif expected is not None and final != expected:
            a.problems.append(
                f"final file size {final} != {expected} bytes written")
    elif final is not None and expected is not None and final < expected:
        a.problems.append(f"device size {final} is smaller than the {expected} written")

    # Occupancy. A flag is not evidence (P1-R17-V-A01).
    fill = rec.get("fill") or {}
    if fill.get("performed"):
        after = (fill.get("after") or {})
        occ = after.get("occupancy")
        want = fill.get("requested_fraction")
        if not after.get("applies", False) or occ is None:
            a.problems.append(
                "fill was performed but no post-fill occupancy was measured")
        elif want is not None and occ < want - FILL_EPS:
            a.problems.append(
                f"post-fill occupancy {occ:.3f} is below the requested "
                f"{want:.3f} -- the card was not filled as claimed")
        else:
            a.derived["fill_occupancy"] = occ
    elif fill.get("requested_fraction") is not None and not fill.get("reason"):
        a.problems.append("a fill fraction was requested but no fill was performed "
                          "and no reason recorded")

    # Elapsed.
    t_first, t_last = rec.get("t_first_monotonic_s"), rec.get("t_last_monotonic_s")
    if t_first is not None and t_last is not None:
        span = t_last - t_first
        if rec.get("elapsed_s") is not None and not _close(rec["elapsed_s"], span,
                                                           ELAPSED_EPS_S):
            a.problems.append(
                f"stored elapsed {rec['elapsed_s']} != {span} from its own "
                f"first/last timestamps")
        if sum(durs) > span + ELAPSED_EPS_S:
            a.problems.append(
                f"window durations sum to {sum(durs):.3f} s, more than the "
                f"{span:.3f} s the run took")


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

    schema = int(rec.get("schema_version", 1))
    a = Audit(path=Path(path), schema=schema, legacy=schema < 2)
    if schema >= 2:
        audit_schema2(rec, a)
    elif schema == 1:
        audit_schema1(rec, a)
    else:
        a.problems.append(f"unknown schema_version {schema}")
        return a

    if a.rates:
        if schema >= 2:
            byts = [w["returned_bytes"] for w in rec["windows"]]
            durs = [w["duration_s"] for w in rec["windows"]]
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
            "short_writes": sum(w.get("short_writes", 0) for w in rec["windows"])
            if schema >= 2 else None,
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
