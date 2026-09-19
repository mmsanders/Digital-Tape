#!/usr/bin/env python3
"""Retained controls for the sustained-write measurement and audit path.

Every check here exists because a specific way of being wrong was found, or
could not be ruled out, in the schema-1 path (P1-R17-V-A01/A02/A03). A control
that cannot go red has not established what it detects, so each one injects the
exact defect it claims to catch and requires the audit to fail AND to name it.

Two things are proven separately:

  the TOOL     write_fully() must loop over short writes rather than assume
               os.write() wrote everything. Proven against an injected writer
               that returns partial counts and against one that stalls at 0.

  the AUDIT    every derived figure comes from primitives, and a mutation of a
               byte count, a timestamp, a final size, an occupancy or a stored
               summary must fail the audit. Proven by mutating a known-good
               synthetic record one field at a time.

No card, device or physical run is involved. The fixture is synthetic and the
five submitted schema-1 files are never written to.

    python3 test_sustained_write.py
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_sustained_write as aud                      # noqa: E402
import measure_sustained_write as msw                    # noqa: E402

MB = 1_000_000
WINDOW_B = 64 * MB
LEGACY = Path(__file__).resolve().parents[1] / "measurements" / \
    "2026-09-16-sustained-write" / "raw"


# --- fixtures ---------------------------------------------------------------

def good_record(n_windows: int = 8, rate_mb_s: float = 40.0,
                filled: bool = True) -> dict:
    """A synthetic schema-2 record that must audit clean."""
    dur = (WINDOW_B / MB) / rate_mb_s
    windows, t = [], 1000.0
    for i in range(n_windows):
        windows.append({
            "index": i,
            "offset_bytes": i * WINDOW_B,
            "requested_bytes": WINDOW_B,
            "returned_bytes": WINDOW_B,
            "write_calls": 1,
            "short_writes": 0,
            "t_start_monotonic_s": t,
            "t_end_monotonic_s": t + dur,
            "duration_s": dur,
            "fsync_ok": True,
            "sync_error": None,
        })
        t += dur
    total = n_windows * WINDOW_B
    cap = 64 * 1000 * MB
    after_fill = {"applies": True, "reason": None, "total_bytes": cap,
                  "free_bytes": int(cap * 0.2), "used_bytes": int(cap * 0.8),
                  "occupancy": 0.8}
    empty = {"applies": True, "reason": None, "total_bytes": cap,
             "free_bytes": cap, "used_bytes": 0, "occupancy": 0.0}
    return {
        "schema_version": 2,
        "target_kind": "mounted-filesystem",
        "measurement_path": "/mnt/card/_seqwrite.bin",
        "measurement_file_retained": True,
        "transfer_mb": n_windows * 64,
        "window_mb": 64,
        "bytes_per_mb": MB,
        "requested_bytes_total": total,
        "returned_bytes_total": total,
        "expected_final_size_bytes": total,
        "final_size_bytes": total,
        "t_first_monotonic_s": 1000.0,
        "t_last_monotonic_s": 1000.0 + n_windows * dur,
        "elapsed_s": n_windows * dur,
        "windows": windows,
        "required_mb_s": msw.REQUIRED_MB_S,
        "required_c90_mb_s": msw.REQUIRED_C90_MB_S,
        "bar_mb_s": msw.BAR_MB_S,
        "fill": {"requested_fraction": 0.8, "performed": filled,
                 "reason": None if filled else "--fill not requested",
                 "before": empty, "after": after_fill if filled else empty,
                 "ballast_bytes": int(cap * 0.8), "ballast_path": "/mnt/card/_ballast.bin"},
        "space_after_measurement": after_fill,
        "sku": "EXAMPLE-PART-64G", "revision": "A", "cid": "deadbeef",
        "sample": "fixture", "reader": "synthetic",
        "measured_at": "2026-09-19T00:00:00+00:00", "host": "synthetic",
    }


def audit_dict(rec: dict) -> aud.Audit:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "run.json"
        p.write_text(json.dumps(rec))
        return aud.audit(p)


def mutated(**changes) -> dict:
    rec = good_record()
    for k, v in changes.items():
        rec[k] = v
    return rec


def expect_red(name: str, rec: dict, marker: str) -> list[str]:
    """The audit must fail, and the failure must name what went wrong."""
    a = audit_dict(rec)
    if a.ok:
        return [f"{name}: audit passed a record with the defect injected"]
    if not any(marker in p for p in a.problems):
        return [f"{name}: failed, but no problem mentions {marker!r}: {a.problems}"]
    return []


def expect_specific(name: str, rec: dict, marker: str) -> list[str]:
    """The targeted failure must survive an unrelated failure being present.

    A control that only fires in isolation cannot be trusted in a real run,
    where more than one thing is usually wrong at once.
    """
    noisy = copy.deepcopy(rec)
    noisy["windows"][-1]["fsync_ok"] = False      # unrelated, always fails
    noisy["windows"][-1]["sync_error"] = "injected unrelated failure"
    a = audit_dict(noisy)
    if not any(marker in p for p in a.problems):
        return [f"{name}: the targeted failure disappeared when an unrelated "
                f"one was present: {a.problems}"]
    return []


# --- controls: the tool -----------------------------------------------------

def the_good_fixture_passes() -> list[str]:
    a = audit_dict(good_record())
    if not a.ok:
        return [f"the clean fixture must audit clean, got {a.problems}"]
    if a.verdict != "PASS":
        return [f"clean fixture at 40 MB/s should PASS the screen, got {a.verdict}"]
    return []


def short_writes_are_looped_not_assumed() -> list[str]:
    """os.write() returning less than asked must not end the window."""
    buf = memoryview(bytearray(1000))
    seen = []

    def stingy(fd, view):            # writes 100 bytes at a time
        n = min(100, len(view))
        seen.append(n)
        return n

    got, calls = msw.write_fully(0, buf, stingy)
    bad = []
    if got != 1000:
        bad.append(f"write_fully returned {got} of 1000 bytes")
    if calls != 10:
        bad.append(f"expected 10 short writes, counted {calls}")
    if sum(seen) != 1000:
        bad.append(f"the injected writer was asked for {sum(seen)} bytes, not 1000")
    return bad


def a_stalled_write_raises_rather_than_spins() -> list[str]:
    def zero(fd, view):
        return 0
    try:
        msw.write_fully(0, memoryview(bytearray(10)), zero)
    except OSError:
        return []
    return ["a writer returning 0 must raise, not loop forever or report success"]


# --- controls: the audit ----------------------------------------------------

def a_short_write_in_the_record_is_caught() -> list[str]:
    rec = good_record()
    rec["windows"][3]["returned_bytes"] = WINDOW_B - 4096      # window not completed
    bad = expect_red("short write", rec, "short write")
    return bad + expect_specific("short write", rec, "short write")


def duration_corruption_is_caught() -> list[str]:
    rec = good_record()
    rec["windows"][2]["duration_s"] *= 0.5        # claims twice the speed
    bad = expect_red("duration", rec, "does not match its own")
    rec2 = good_record()
    rec2["windows"][2]["t_end_monotonic_s"] = rec2["windows"][2]["t_start_monotonic_s"]
    bad += expect_red("timestamp", rec2, "is not after start")
    rec3 = good_record()
    rec3["windows"][4]["t_start_monotonic_s"] -= 5.0            # out of order
    bad += expect_red("ordering", rec3, "before the previous window ended")
    return bad + expect_specific("duration", rec, "does not match its own")


def byte_count_mismatch_is_caught() -> list[str]:
    rec = mutated(returned_bytes_total=99)
    bad = expect_red("byte total", rec, "its own windows account for")
    rec2 = good_record()
    rec2["windows"] = rec2["windows"][:-1]        # one window short of the transfer
    bad += expect_red("transfer size", rec2, "not the size it claims")
    return bad + expect_specific("byte total", rec, "its own windows account for")


def final_size_mismatch_is_caught() -> list[str]:
    rec = mutated(final_size_bytes=123)
    bad = expect_red("final size", rec, "final file size")
    rec2 = mutated(measurement_file_retained=False)
    bad += expect_red("deleted file", rec2, "deleted")
    rec3 = mutated(final_size_bytes=None)
    bad += expect_red("missing size", rec3, "no final measurement-file size")
    return bad + expect_specific("final size", rec, "final file size")


def a_false_or_missing_fill_is_caught() -> list[str]:
    rec = good_record()
    rec["fill"]["after"]["occupancy"] = 0.31      # claimed 80%, measured 31%
    bad = expect_red("false fill", rec, "was not filled as claimed")

    rec2 = good_record()
    rec2["fill"]["after"]["occupancy"] = None     # flag set, nothing measured
    bad += expect_red("unmeasured fill", rec2, "no post-fill occupancy")

    rec3 = good_record()
    rec3["fill"]["after"] = {"applies": False, "reason": "invented",
                             "total_bytes": 1, "free_bytes": None,
                             "used_bytes": None, "occupancy": None}
    bad += expect_red("inapplicable fill", rec3, "no post-fill occupancy")
    return bad + expect_specific("false fill", rec, "was not filled as claimed")


def summary_tampering_is_caught_in_legacy_records() -> list[str]:
    """The exact P1-R17-V-A02 mutation: 38.79 -> 999.0 must not pass."""
    src = LEGACY / "pny1.json"
    if not src.exists():
        return [f"legacy fixture missing: {src}"]
    rec = json.loads(src.read_text())
    clean = audit_dict(rec)
    if not clean.ok:
        return [f"the unmodified legacy record must audit clean: {clean.problems}"]
    if not clean.legacy:
        return ["a schema-1 record must be reported as legacy"]

    bad = []
    tampered = dict(rec, mean_mb_s=999.0)
    bad += expect_red("legacy mean", tampered, "stored mean_mb_s")
    bad += expect_red("legacy worst", dict(rec, worst_window_mb_s=99.0),
                      "stored worst_window_mb_s")
    bad += expect_red("legacy verdict", dict(rec, verdict="FAIL"), "stored verdict")
    bad += expect_red("legacy median", dict(rec, median_mb_s=1.0), "stored median_mb_s")

    # And the derived figures must not move when a summary field is mutated.
    after = audit_dict(tampered)
    if abs(after.derived["worst"] - clean.derived["worst"]) > 1e-9:
        bad.append("a stored-summary mutation changed a derived figure")
    return bad


def every_adjacent_pair_is_what_is_computed() -> list[str]:
    """P1-R17-V-A03: sliding pairs must include (1,2), (3,4)...

    Built so the two slow windows straddle a phase boundary: the fixed
    phase-0 pairs (0,1) and (2,3) each pair one slow window with a fast one and
    never see them together, while the sliding pair (1,2) does. One slow window
    alone would not distinguish the two statistics -- both phases would contain
    it -- which is exactly why this vector has two.
    """
    rates = [100.0, 10.0, 10.0, 100.0, 100.0, 100.0]
    byts = [WINDOW_B] * len(rates)
    durs = [(WINDOW_B / MB) / r for r in rates]
    sliding = aud.sliding_pair_rates(rates, byts, durs)
    fixed = aud.fixed_phase0_pair_rates(rates, byts, durs)
    bad = []
    if len(sliding) != len(rates) - 1:
        bad.append(f"expected {len(rates)-1} sliding pairs, got {len(sliding)}")
    if min(sliding) >= min(fixed) - 1e-9:
        bad.append("the sliding minimum should be below the fixed-pair minimum "
                   "on a vector whose worst pair straddles a phase boundary")

    # The values Verification independently computed for the onn control, which
    # is the case that made this a finding at all.
    onn = LEGACY / "onn-v10.json"
    if onn.exists():
        a = aud.audit(onn)
        for key, want in (("pair_min_sliding", 17.76235),
                          ("pair_min_fixed_phase0", 18.00776)):
            got = a.derived[key]
            if abs(got - want) > 5e-5:
                bad.append(f"onn {key}: {got:.5f} != independently reported {want}")
    return bad


def an_unreadable_record_fails() -> list[str]:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "broken.json"
        p.write_text("{not json")
        a = aud.audit(p)
        if a.ok:
            return ["malformed JSON must fail the audit"]
    return []


CONTROLS = (
    the_good_fixture_passes,
    short_writes_are_looped_not_assumed,
    a_stalled_write_raises_rather_than_spins,
    a_short_write_in_the_record_is_caught,
    duration_corruption_is_caught,
    byte_count_mismatch_is_caught,
    final_size_mismatch_is_caught,
    a_false_or_missing_fill_is_caught,
    summary_tampering_is_caught_in_legacy_records,
    every_adjacent_pair_is_what_is_computed,
    an_unreadable_record_fails,
)


def main() -> int:
    failures = []
    for c in CONTROLS:
        for problem in c():
            failures.append(f"{c.__name__}: {problem}")
    if failures:
        for f in failures:
            print(f"FAIL sustained-write control: {f}", file=sys.stderr)
        return 1
    print(f"OK  sustained-write: {len(CONTROLS)} retained controls pass; "
          f"short writes, timestamps, byte/size accounting, fill occupancy, "
          f"summary tampering and the adjacent-pair definition all go red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
