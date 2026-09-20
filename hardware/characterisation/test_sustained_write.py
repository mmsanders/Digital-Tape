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

P1-R21-V01 added a second requirement: a malformed record must be rejected BY
REPORT, never by traceback. Each of the fifteen malformed forms the independent
audit found accepted or crashing is reproduced here as its own control,
asserting the message names the field it is about -- so none of them can pass
because an unrelated check happened to fail on the same record. Each was
confirmed red against the rejected head before being recorded green here.

"""

from __future__ import annotations

import copy
import json
import subprocess
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
                filled: bool = True, short_at: int | None = None) -> dict:
    """A synthetic schema-2 record that must audit clean.

    `short_at` splits that window into two write calls, so the short-write
    path is exercised by a fixture that still has to pass every check.
    """
    dur = (WINDOW_B / MB) / rate_mb_s
    windows, trace, t, offset = [], [], 1000.0, 0
    for i in range(n_windows):
        if i == short_at:
            parts = [(WINDOW_B, WINDOW_B - 4096), (4096, 4096)]
        else:
            parts = [(WINDOW_B, WINDOW_B)]
        start = offset
        for req, got in parts:
            trace.append({
                "seq": len(trace),
                "window": i,
                "offset_bytes": offset,
                "requested_bytes": req,
                "returned_bytes": got,
            })
            offset += got
        windows.append({
            "index": i,
            "offset_start_bytes": start,
            "offset_end_bytes": offset,
            "requested_bytes": WINDOW_B,
            "returned_bytes": offset - start,
            "write_calls": len(parts),
            "short_writes": len(parts) - 1,
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
                  "occupancy": int(cap * 0.8) / cap}
    empty = {"applies": True, "reason": None, "total_bytes": cap,
             "free_bytes": cap, "used_bytes": 0, "occupancy": 0.0}
    end = dict(after_fill)
    end["used_bytes"] = after_fill["used_bytes"] + total
    end["free_bytes"] = cap - end["used_bytes"]
    end["occupancy"] = end["used_bytes"] / cap
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
        "t_last_monotonic_s": 1000.0 + n_windows * dur + 0.02,
        "elapsed_s": n_windows * dur + 0.02,
        "final_fsync": {"attempted": True, "ok": True, "error": None,
                        "t_start_monotonic_s": 1000.0 + n_windows * dur,
                        "t_end_monotonic_s": 1000.0 + n_windows * dur + 0.01},
        "windows": windows,
        "write_trace": trace,
        "write_trace_sha256": aud._trace_digest(trace),
        "required_mb_s": msw.REQUIRED_MB_S,
        "required_c90_mb_s": msw.REQUIRED_C90_MB_S,
        "bar_mb_s": msw.BAR_MB_S,
        "fill": {"requested_fraction": 0.8, "performed": filled,
                 "reason": None if filled else "--fill not requested",
                 "before": empty, "after": after_fill if filled else empty,
                 "ballast_bytes": int(cap * 0.8) if filled else 0,
                 "ballast_path": "/mnt/card/_ballast.bin" if filled else None},
        "space_after_measurement": end,
        "sku": "EXAMPLE-PART-64G", "revision": "A", "cid": "deadbeef",
        "sample": "fixture", "reader": "synthetic",
        "measured_at": "2026-09-19T00:00:00+00:00", "host": "synthetic",
    }


def rebind(rec: dict) -> dict:
    """Recompute the trace digest -- for mutations that legitimately change it."""
    rec["write_trace_sha256"] = aud._trace_digest(rec["write_trace"])
    return rec


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

    calls = msw.write_fully(0, buf, 4096, stingy)
    bad = []
    got = sum(c["returned_bytes"] for c in calls)
    if got != 1000:
        bad.append(f"write_fully returned {got} of 1000 bytes")
    if len(calls) != 10:
        bad.append(f"expected 10 short writes, counted {len(calls)}")
    if sum(seen) != 1000:
        bad.append(f"the injected writer was asked for {sum(seen)} bytes, not 1000")
    # Every call must carry the offset it actually wrote at (P1-R19-V01).
    want = 4096
    for c in calls:
        if c["offset_bytes"] != want:
            bad.append(f"call at offset {c['offset_bytes']}, expected {want}")
            break
        if c["requested_bytes"] != 1000 - (want - 4096):
            bad.append(f"call requested {c['requested_bytes']}, expected the "
                       f"remaining {1000 - (want - 4096)}")
            break
        want += c["returned_bytes"]
    return bad


def a_stalled_write_raises_rather_than_spins() -> list[str]:
    def zero(fd, view):
        return 0
    try:
        msw.write_fully(0, memoryview(bytearray(10)), 0, zero)
    except OSError:
        return []
    return ["a writer returning 0 must raise, not loop forever or report success"]


# --- controls: the audit ----------------------------------------------------

def _drop(rec: dict, *keys) -> dict:
    for k in keys:
        rec.pop(k, None)
    return rec


def the_schema_is_closed() -> list[str]:
    """P1-R19-V02: a missing or unknown mandatory field must not pass.

    The old auditor read the fields it recognised and ignored the rest, so
    deleting one was invisible. Every required field is now dropped in turn and
    each must be caught by name.
    """
    bad = []
    for key in sorted(aud.S2_REQUIRED):
        rec = _drop(good_record(), key)
        a = audit_dict(rec)
        if a.ok:
            bad.append(f"dropping required field {key!r} passed the audit")
        elif not any(key in p for p in a.problems):
            bad.append(f"dropping {key!r} failed without naming it: {a.problems}")
    rec = good_record()
    rec["something_invented"] = 1
    if audit_dict(rec).ok:
        bad.append("an unknown top-level field passed a closed schema")
    rec = good_record()
    del rec["windows"][2]["fsync_ok"]
    a = audit_dict(rec)
    if a.ok:
        bad.append("a missing fsync_ok passed -- it must not read as success")
    return bad


def a_false_summary_is_rejected_not_ignored() -> list[str]:
    """The audit's own mutation: an inserted worst_window_mb_s = 999.0."""
    bad = []
    for field, value in (("worst_window_mb_s", 999.0), ("mean_mb_s", 999.0),
                         ("verdict", "PASS"), ("windows_mb_s", [1, 2])):
        rec = good_record()
        rec[field] = value
        a = audit_dict(rec)
        if a.ok:
            bad.append(f"a stored {field!r} passed; schema 2 holds primitives "
                       f"and a summary in the file is a contradiction")
        elif not any(field in p for p in a.problems):
            bad.append(f"the {field!r} rejection does not name it: {a.problems}")
    return bad


def an_invented_target_kind_cannot_evade_the_size_branch() -> list[str]:
    bad = []
    rec = good_record()
    rec["target_kind"] = "something-else"
    a = audit_dict(rec)
    if a.ok:
        bad.append("an invented target_kind passed and skipped the final-size "
                   "branch entirely")
    elif not any("target_kind" in p for p in a.problems):
        bad.append(f"the failure does not name target_kind: {a.problems}")

    # The raw-device branch must be enforced, not merely declared.
    rec = good_record()
    rec["target_kind"] = "raw-device"          # still claims a retained file
    if audit_dict(rec).ok:
        bad.append("a raw-device record claiming a retained measurement file "
                   "passed")
    rec = good_record()
    rec["target_kind"] = "raw-device"
    rec["measurement_file_retained"] = False
    rec["final_size_bytes"] = rec["expected_final_size_bytes"] - 1
    if audit_dict(rec).ok:
        bad.append("a device smaller than the transfer passed")
    return bad


def the_write_trace_is_proven_not_believed() -> list[str]:
    """P1-R19-V01, every mutation the finding asked for."""
    bad = []

    def red(name, rec, marker, rebind_digest=False):
        if rebind_digest:
            rebind(rec)
        a = audit_dict(rec)
        if a.ok:
            bad.append(f"{name}: passed")
        elif not any(marker in p for p in a.problems):
            bad.append(f"{name}: failed without naming {marker!r}: {a.problems}")

    rec = good_record()
    rec["write_trace"] = rec["write_trace"][:-1]
    red("a missing call", rec, "trace covers", rebind_digest=True)

    rec = good_record()
    rec["write_trace"].append(dict(rec["write_trace"][-1]))
    rec["write_trace"][-1]["seq"] = len(rec["write_trace"]) - 1
    red("a duplicated call", rec, "offset", rebind_digest=True)

    rec = good_record(short_at=2)
    w = [c for c in rec["write_trace"] if c["window"] == 2]
    i, j = w[0]["seq"], w[1]["seq"]
    rec["write_trace"][i], rec["write_trace"][j] = \
        rec["write_trace"][j], rec["write_trace"][i]
    rec["write_trace"][i]["seq"], rec["write_trace"][j]["seq"] = i, j
    red("a reordered pair", rec, "offset", rebind_digest=True)

    rec = good_record(short_at=2)
    w = [c for c in rec["write_trace"] if c["window"] == 2][1]
    w["offset_bytes"] += 7
    red("a continuation at the wrong offset", rec,
        "resume where the short write stopped", rebind_digest=True)

    rec = good_record()
    rec["write_trace"][4]["returned_bytes"] += 1024
    red("an over-return", rec, "more than the", rebind_digest=True)

    rec = good_record()
    rec["write_trace"][4]["returned_bytes"] = 0
    red("a call that wrote nothing", rec, "not progress", rebind_digest=True)

    rec = good_record()
    rec["write_trace"][2]["returned_bytes"] -= 512   # digest NOT rebound
    red("an edited trace", rec, "write_trace_sha256")

    rec = good_record()
    rec["windows"][3]["write_calls"] = 99
    red("an untruthful call count", rec, "write_calls")

    rec = good_record()
    rec["windows"][3]["short_writes"] = 99
    red("an untruthful short-write count", rec, "short_writes")

    rec = good_record()
    rec["write_trace"] = []
    red("no trace at all", rec, "write_trace", rebind_digest=True)
    return bad


def window_order_and_offsets_are_enforced() -> list[str]:
    bad = []

    def red(name, rec, marker):
        a = audit_dict(rec)
        if a.ok:
            bad.append(f"{name}: passed")
        elif not any(marker in p for p in a.problems):
            bad.append(f"{name}: failed without naming {marker!r}: {a.problems}")

    rec = good_record()
    rec["windows"][3]["index"] = 9
    red("a wrong index", rec, "out of order")

    rec = good_record()
    rec["windows"][3]["offset_start_bytes"] = 7
    red("a wrong start offset", rec, "not contiguous")

    rec = good_record()
    rec["windows"][3]["offset_end_bytes"] += 4096
    red("an end offset that does not follow", rec, "end offset")

    rec = good_record()
    rec["windows"][2], rec["windows"][3] = rec["windows"][3], rec["windows"][2]
    red("two windows swapped", rec, "out of order")
    return bad


def timing_and_the_closing_flush_are_enforced() -> list[str]:
    bad = []

    def red(name, rec, marker):
        a = audit_dict(rec)
        if a.ok:
            bad.append(f"{name}: passed")
        elif not any(marker in p for p in a.problems):
            bad.append(f"{name}: failed without naming {marker!r}: {a.problems}")

    rec = good_record()
    rec["windows"][2]["duration_s"] *= 0.5
    red("a corrupt duration", rec, "does not match its own")

    rec = good_record()
    rec["windows"][2]["t_end_monotonic_s"] = rec["windows"][2]["t_start_monotonic_s"]
    red("an inverted window", rec, "not after start")

    rec = good_record()
    rec["windows"][4]["t_start_monotonic_s"] -= 5.0
    red("overlapping windows", rec, "before the previous window ended")

    rec = good_record()
    rec["elapsed_s"] *= 2
    red("a corrupt elapsed", rec, "elapsed")

    rec = good_record()
    fs = rec["final_fsync"]
    fs["t_start_monotonic_s"] = rec["t_last_monotonic_s"] + 1.0
    fs["t_end_monotonic_s"] = rec["t_last_monotonic_s"] + 2.0
    red("a closing flush after the clock stopped", rec, "outside the measured span")

    rec = good_record()
    rec["final_fsync"]["ok"] = False
    red("a failed closing flush", rec, "closing fsync failed")

    rec = good_record()
    rec["final_fsync"]["attempted"] = False
    red("no closing flush", rec, "no closing fsync")
    return bad


def totals_and_final_size_are_enforced() -> list[str]:
    bad = []

    def red(name, rec, marker):
        a = audit_dict(rec)
        if a.ok:
            bad.append(f"{name}: passed")
        elif not any(marker in p for p in a.problems):
            bad.append(f"{name}: failed without naming {marker!r}: {a.problems}")

    rec = good_record()
    rec["requested_bytes_total"] = 99
    red("a wrong requested total", rec, "requested_bytes_total")

    rec = good_record()
    rec["returned_bytes_total"] = 99
    red("a wrong returned total", rec, "returned_bytes_total")

    rec = good_record()
    rec["expected_final_size_bytes"] += 4096
    red("a transfer that is not its declared size", rec, "expected")

    rec = good_record()
    rec["final_size_bytes"] = 123
    red("a wrong final size", rec, "final file size")

    rec = good_record()
    rec["measurement_file_retained"] = False
    red("a deleted measurement file", rec, "deleted")
    return bad


def capacity_accounting_is_enforced() -> list[str]:
    bad = []

    def red(name, rec, marker):
        a = audit_dict(rec)
        if a.ok:
            bad.append(f"{name}: passed")
        elif not any(marker in p for p in a.problems):
            bad.append(f"{name}: failed without naming {marker!r}: {a.problems}")

    rec = good_record()
    rec["space_after_measurement"]["occupancy"] = 0.01
    red("occupancy that does not equal used/total", rec, "occupancy")

    rec = good_record()
    sp = rec["space_after_measurement"]
    sp["used_bytes"] = sp["total_bytes"]
    sp["free_bytes"] = sp["total_bytes"]
    sp["occupancy"] = 1.0
    red("used + free beyond total", rec, "exceeds total")

    rec = good_record()
    rec["space_after_measurement"]["used_bytes"] = 0
    rec["space_after_measurement"]["occupancy"] = 0.0
    red("used space that shrank across the run", rec, "shrank")

    rec = good_record()
    rec["fill"]["after"]["occupancy"] = 0.31
    red("a false fill", rec, "was not filled as claimed")

    rec = good_record()
    rec["fill"]["after"] = {"applies": False, "reason": "invented",
                            "total_bytes": 1, "free_bytes": None,
                            "used_bytes": None, "occupancy": None}
    red("filesystem accounting declared inapplicable on a filesystem", rec,
        "inapplicable")

    rec = good_record()
    rec["fill"]["before"]["used_bytes"] = rec["fill"]["after"]["used_bytes"] + 1
    rec["fill"]["before"]["occupancy"] = (rec["fill"]["before"]["used_bytes"]
                                          / rec["fill"]["before"]["total_bytes"])
    red("a fill that removed data", rec, "less used space")
    return bad


def the_controls_stay_specific_under_noise() -> list[str]:
    """Each targeted failure must survive an unrelated one being present."""
    bad = []
    cases = [
        ("trace", lambda r: r["write_trace"].pop(), "trace covers"),
        ("offsets", lambda r: r["windows"][3].__setitem__("offset_start_bytes", 7),
         "not contiguous"),
        ("totals", lambda r: r.__setitem__("returned_bytes_total", 99),
         "returned_bytes_total"),
    ]
    for name, mutate, marker in cases:
        rec = good_record()
        mutate(rec)
        rebind(rec)
        rec["windows"][-1]["fsync_ok"] = False        # unrelated, always fails
        rec["windows"][-1]["sync_error"] = "injected unrelated failure"
        a = audit_dict(rec)
        if not any(marker in p for p in a.problems):
            bad.append(f"{name}: the targeted failure vanished under unrelated "
                       f"noise: {a.problems}")
    return bad


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


# --- P1-R21-V01: the malformed forms the independent audit found open -------
#
# Verification generated a schema-2 fixture and mutated it one property at a
# time. Thirteen malformed forms were ACCEPTED and one crashed the auditor with
# an uncaught TypeError. Each of those forms is reproduced below as its own
# retained control, and each asserts the message names the field it is about --
# so a control cannot pass because some unrelated check happened to fail on the
# same record.
#
# The crash matters separately from the acceptances: an audit that dies by
# traceback has not reported anything, and a verifier cannot tell a crash from
# a tool it invoked wrongly. Every form here must leave a problem report the
# auditor owns.

def _deep() -> dict:
    """A fresh, clean fixture for each mutation; nothing leaks between them."""
    return copy.deepcopy(good_record())


def expect_controlled_red(name: str, rec: dict, marker: str) -> list[str]:
    """Rejected by report, never by traceback, and the report must be specific."""
    try:
        a = audit_dict(rec)
    except Exception as exc:                       # noqa: BLE001 -- that is the point
        return [f"{name}: the audit raised {type(exc).__name__}: {exc} -- a "
                f"malformed record must produce a problem report the auditor "
                f"owns, not a traceback"]
    if a.ok:
        return [f"{name}: audit passed a record with the defect injected"]
    if not any(marker in p for p in a.problems):
        return [f"{name}: failed, but no problem mentions {marker!r}: "
                f"{a.problems}"]
    return []


def the_closing_flush_interval_must_run_forwards() -> list[str]:
    """A flush whose end precedes its start proves no ordered durability event."""
    rec = _deep()
    fs = rec["final_fsync"]
    fs["t_start_monotonic_s"], fs["t_end_monotonic_s"] = \
        fs["t_end_monotonic_s"], fs["t_start_monotonic_s"]
    bad = expect_controlled_red("reversed closing fsync", rec,
                                "before it starts")
    # ... and the honest interval must still pass, or the check is just noise.
    if not audit_dict(_deep()).ok:
        bad.append("the unmutated fixture stopped passing")
    return bad


def the_closing_flush_object_is_closed() -> list[str]:
    bad = []
    rec = _deep()
    del rec["final_fsync"]["error"]
    bad += expect_controlled_red("final_fsync.error removed", rec,
                                 "missing required field 'error'")
    rec = _deep()
    rec["final_fsync"]["duration_s"] = 0.01
    bad += expect_controlled_red("unknown final_fsync member", rec,
                                 "unknown field 'duration_s'")
    rec = _deep()
    rec["final_fsync"]["ok"] = True
    rec["final_fsync"]["error"] = "ENOSPC"
    bad += expect_controlled_red("fsync both ok and errored", rec,
                                 "one of the two is untrue")
    return bad


def a_malformed_timestamp_is_reported_not_raised() -> list[str]:
    """The exact crash in P1-R21-V01, plus the other timestamps it reaches."""
    bad = []
    rec = _deep()
    rec["final_fsync"]["t_start_monotonic_s"] = "1000.0"
    bad += expect_controlled_red("string final_fsync.t_start_monotonic_s", rec,
                                 "final_fsync: t_start_monotonic_s")
    rec = _deep()
    rec["final_fsync"]["t_end_monotonic_s"] = None
    bad += expect_controlled_red("null final_fsync.t_end_monotonic_s", rec,
                                 "final_fsync: t_end_monotonic_s")
    rec = _deep()
    rec["t_last_monotonic_s"] = "later"
    bad += expect_controlled_red("string top-level timestamp", rec,
                                 "t_last_monotonic_s")
    rec = _deep()
    rec["windows"][2]["t_end_monotonic_s"] = "soon"
    bad += expect_controlled_red("string window timestamp", rec,
                                 "window 2: t_end_monotonic_s")
    rec = _deep()
    rec["windows"][2]["duration_s"] = float("nan")
    bad += expect_controlled_red("NaN window duration", rec, "not finite")
    rec = _deep()
    rec["t_last_monotonic_s"] = float("inf")
    bad += expect_controlled_red("infinite top-level timestamp", rec,
                                 "not finite")
    return bad


def a_boolean_is_not_an_integer_identity() -> list[str]:
    """`True == 1` in Python; it must not be 1 in a record that proves order.

    The digest is rebound in each case, so nothing but the type check can be
    what catches these.
    """
    bad = []
    rec = _deep()
    rec["write_trace"][0]["seq"] = False           # was 0
    bad += expect_controlled_red("boolean write_trace.seq", rebind(rec),
                                 "write call 0: seq")
    rec = _deep()
    rec["write_trace"][1]["window"] = True         # was 1
    bad += expect_controlled_red("boolean write_trace.window", rebind(rec),
                                 "write call 1: window")
    rec = _deep()
    rec["windows"][1]["index"] = True              # was 1
    bad += expect_controlled_red("boolean window index", rec, "window 1: index")
    rec = _deep()
    rec["windows"][0]["short_writes"] = False      # was 0
    bad += expect_controlled_red("boolean short_writes", rec,
                                 "window 0: short_writes")
    return bad


def an_integral_float_is_not_an_integer_byte_count() -> list[str]:
    """1.0 is not 1 for a byte count: it has been through a lossy path."""
    bad = []
    rec = _deep()
    rec["windows"][1]["offset_start_bytes"] = float(
        rec["windows"][1]["offset_start_bytes"])
    bad += expect_controlled_red("float byte offset", rec,
                                 "window 1: offset_start_bytes")
    rec = _deep()
    rec["returned_bytes_total"] = float(rec["returned_bytes_total"])
    bad += expect_controlled_red("float byte total", rec,
                                 "returned_bytes_total")
    rec = _deep()
    rec["windows"][0]["write_calls"] = 1.0
    bad += expect_controlled_red("float call count", rec,
                                 "window 0: write_calls")
    rec = _deep()
    rec["space_after_measurement"]["total_bytes"] = float(
        rec["space_after_measurement"]["total_bytes"])
    bad += expect_controlled_red("float capacity", rec,
                                 "space_after_measurement: total_bytes")
    rec = _deep()
    rec["fill"]["before"]["used_bytes"] = 0.0
    bad += expect_controlled_red("float capacity in fill.before", rec,
                                 "fill.before: used_bytes")
    rec = _deep()
    rec["write_trace"][0]["returned_bytes"] = float(
        rec["write_trace"][0]["returned_bytes"])
    bad += expect_controlled_red("float in a write call", rebind(rec),
                                 "write call 0: returned_bytes")
    rec = _deep()
    rec["final_size_bytes"] = -1
    bad += expect_controlled_red("negative final size", rec,
                                 "final_size_bytes is negative")
    return bad


def the_declared_window_size_must_match_the_windows() -> list[str]:
    """`window_mb` was accepted while the retained windows contradicted it."""
    bad = []
    rec = _deep()
    rec["window_mb"] = 32                          # the windows are 64 MB
    bad += expect_controlled_red("false window_mb", rec, "window_mb")
    rec = _deep()
    rec["window_mb"] = 0
    bad += expect_controlled_red("zero window_mb", rec, "not a positive size")
    rec = _deep()
    rec["windows"][2]["requested_bytes"] -= MB     # a SHORT window mid-run
    rec["windows"][2]["returned_bytes"] -= MB
    bad += expect_controlled_red("short window mid-run", rec,
                                 "only the final window may be short")

    # A genuinely short FINAL window is how every real run ends when the
    # transfer is not a whole number of windows. The rule must not reject it,
    # or it is stricter than the method and would fail an honest record.
    rec = _deep()
    trim = MB                                      # one whole MB, so transfer_mb stays exact
    last, call = rec["windows"][-1], rec["write_trace"][-1]
    last["requested_bytes"] -= trim
    last["returned_bytes"] -= trim
    last["offset_end_bytes"] -= trim
    call["requested_bytes"] -= trim
    call["returned_bytes"] -= trim
    for key in ("requested_bytes_total", "returned_bytes_total",
                "expected_final_size_bytes", "final_size_bytes"):
        rec[key] -= trim
    rec["transfer_mb"] -= 1
    a = audit_dict(rebind(rec))
    if not a.ok:
        bad.append(f"a legitimately short FINAL window was rejected: "
                   f"{a.problems}")
    return bad


def the_declared_criteria_must_be_the_methods() -> list[str]:
    """A record that carries its own bar can otherwise move the bar."""
    bad = []
    for name, wrong in (("required_mb_s", 1.0),
                        ("required_c90_mb_s", 1.0),
                        ("bar_mb_s", 1.0)):
        rec = _deep()
        rec[name] = wrong
        bad += expect_controlled_red(f"false {name}", rec, name)
    # And the auditor's own constants must be the method's, restated here a
    # third time rather than read back out of either module.
    for name, want in (("REQUIRED_MB_S", 21.2), ("REQUIRED_C90_MB_S", 31.75),
                       ("BAR_MB_S", 23.3)):
        got = getattr(aud, name)
        if got != want:
            bad.append(f"the auditor's {name} is {got}, not the method's {want}")
        if getattr(msw, name) != want:
            bad.append(f"the tool's {name} is {getattr(msw, name)}, not {want}")
    return bad


def the_nested_capacity_objects_are_closed() -> list[str]:
    bad = []
    rec = _deep()
    rec["fill"]["hurried"] = True
    bad += expect_controlled_red("unknown fill member", rec,
                                 "fill: unknown field 'hurried'")
    rec = _deep()
    rec["space_after_measurement"]["trimmed"] = False
    bad += expect_controlled_red("unknown space member", rec,
                                 "space_after_measurement: unknown field "
                                 "'trimmed'")
    rec = _deep()
    rec["fill"]["after"]["headroom_bytes"] = 1
    bad += expect_controlled_red("unknown fill.after member", rec,
                                 "fill.after: unknown field 'headroom_bytes'")
    rec = _deep()
    del rec["fill"]["ballast_path"]
    bad += expect_controlled_red("missing fill member", rec,
                                 "fill: missing required field 'ballast_path'")
    rec = _deep()
    del rec["space_after_measurement"]["occupancy"]
    bad += expect_controlled_red("missing capacity member", rec,
                                 "space_after_measurement: missing required "
                                 "field 'occupancy'")
    rec = _deep()
    rec["fill"]["performed"] = "yes"
    bad += expect_controlled_red("non-boolean fill.performed", rec,
                                 "fill: performed must be a boolean")
    rec = _deep()
    rec["fill"]["requested_fraction"] = 1.5
    bad += expect_controlled_red("out-of-range fill fraction", rec,
                                 "not a fraction in (0, 1]")
    return bad


def a_figure_that_cannot_be_measured_must_be_null() -> list[str]:
    """A raw device has no filesystem accounting; inventing one is fabrication."""
    rec = _deep()
    rec["space_after_measurement"] = {
        "applies": False, "reason": "raw block device: no filesystem accounting",
        "total_bytes": 64 * 1000 * MB,
        # fabricated: these cannot be measured on a block device
        "free_bytes": 1, "used_bytes": 2, "occupancy": 0.5,
    }
    return expect_controlled_red("fabricated raw-device accounting", rec,
                                 "must be null, not fabricated")


def an_honest_raw_device_record_still_passes() -> list[str]:
    """Closing a schema must not reject the records it exists to accept.

    The raw-device branch is where the new null-rather-than-fabricated rule
    bites, and it has no fixture of its own elsewhere in this suite. A check
    that fails closed on legitimate input is as much a defect as one that
    fails open on malformed input -- it just fails later, on a real card.
    """
    cap = 64 * 1000 * MB
    raw_space = {"applies": False,
                 "reason": "raw block device: no filesystem free/used accounting",
                 "total_bytes": cap, "free_bytes": None, "used_bytes": None,
                 "occupancy": None}
    rec = _deep()
    rec["target_kind"] = "raw-device"
    rec["measurement_file_retained"] = False
    rec["measurement_path"] = "/dev/sdb"
    rec["final_size_bytes"] = cap
    rec["space_after_measurement"] = copy.deepcopy(raw_space)
    rec["fill"] = {"requested_fraction": 0.8, "performed": False,
                   "reason": "raw block device: the whole device is written anyway",
                   "before": copy.deepcopy(raw_space),
                   "after": copy.deepcopy(raw_space),
                   "ballast_bytes": 0, "ballast_path": None}
    a = audit_dict(rec)
    if not a.ok:
        return [f"a legitimate raw-device record was rejected: {a.problems}"]
    return []


def every_p1_r21_form_is_covered_and_none_of_them_crash() -> list[str]:
    """The finding's own list, checked as a list rather than as prose.

    If a later round deletes one of the controls above, this goes red naming
    the form that stopped being covered.
    """
    required = {
        "reversed closing fsync": the_closing_flush_interval_must_run_forwards,
        "final_fsync.error removed": the_closing_flush_object_is_closed,
        "unknown final_fsync member": the_closing_flush_object_is_closed,
        "string final_fsync.t_start_monotonic_s":
            a_malformed_timestamp_is_reported_not_raised,
        "boolean write_trace.seq": a_boolean_is_not_an_integer_identity,
        "boolean window index": a_boolean_is_not_an_integer_identity,
        "float byte offset": an_integral_float_is_not_an_integer_byte_count,
        "float byte total": an_integral_float_is_not_an_integer_byte_count,
        "float capacity": an_integral_float_is_not_an_integer_byte_count,
        "false window_mb": the_declared_window_size_must_match_the_windows,
        "false required_mb_s": the_declared_criteria_must_be_the_methods,
        "false required_c90_mb_s": the_declared_criteria_must_be_the_methods,
        "false bar_mb_s": the_declared_criteria_must_be_the_methods,
        "unknown fill member": the_nested_capacity_objects_are_closed,
        "unknown space member": the_nested_capacity_objects_are_closed,
    }
    bad = []
    for form, control in sorted(required.items()):
        if control not in CONTROLS:
            bad.append(f"{form!r} is covered by {control.__name__}, which is "
                       f"no longer in the retained suite")
    return bad


# --- P1-R23-V01: what the repaired auditor still let through -----------------
#
# The independent re-audit closed every form P1-R21-V01 named and then found
# eleven one-field neighbours still open: three terminated the audit by
# traceback, eight passed. The root of all eleven is the same -- the auditor did
# not establish that its input WAS a schema-2 record before doing arithmetic on
# it. It coerced the declared version, it let schema 3 in through a `>=`, it
# divided by denominators it had not checked (and, in one case, by a denominator
# it had already reported as invalid), and it required the seven identity fields
# to be present without ever requiring them to be strings.
#
# Each case below is reproduced as its own control, asserting the message names
# the field, so none can pass because an unrelated check fired on the same
# record. Each was confirmed against the rejected head before being recorded.

def _json_audit(payload) -> "aud.Audit":
    """Audit an arbitrary JSON document, not just a record-shaped dict."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "run.json"
        p.write_text(json.dumps(payload))
        return aud.audit(p)


def a_denominator_is_checked_before_it_divides() -> list[str]:
    """Two ZeroDivisionErrors, and the worse of the two.

    `bytes_per_mb = 0` reached the per-window rate division. The capacity case
    is the one worth staring at: the auditor **reported** a non-positive
    `total_bytes` as a problem and then divided by it one check later. Noticing
    a bad value and then using it anyway is worse than not checking, because the
    traceback comes from code that had already been right.
    """
    bad = []
    rec = _deep()
    rec["bytes_per_mb"] = 0
    bad += expect_controlled_red("bytes_per_mb = 0", rec, "bytes_per_mb")
    rec = _deep()
    rec["space_after_measurement"]["total_bytes"] = 0
    bad += expect_controlled_red("capacity total_bytes = 0", rec, "total_bytes")
    rec = _deep()
    rec["fill"]["before"]["total_bytes"] = 0
    bad += expect_controlled_red("fill.before total_bytes = 0", rec,
                                 "fill.before: total_bytes")
    rec = _deep()
    rec["bytes_per_mb"] = -1_000_000
    bad += expect_controlled_red("negative bytes_per_mb", rec, "bytes_per_mb")
    rec = _deep()
    rec["transfer_mb"] = 0
    bad += expect_controlled_red("transfer_mb = 0", rec, "transfer_mb")
    return bad


def the_declared_version_is_not_coerced() -> list[str]:
    """`int("bogus")` raised before anything had checked the type."""
    bad = []
    for value in ("bogus", None, 2.0, [2], {"v": 2}, True):
        rec = _deep()
        rec["schema_version"] = value
        bad += expect_controlled_red(f"schema_version = {value!r}", rec,
                                     "schema_version")
    return bad


def an_undefined_schema_version_is_not_audited_as_schema_2() -> list[str]:
    """`schema >= 2` let 3 in through the schema-2 door.

    This method documents exactly 1 and 2. Auditing an undeclared version
    against the schema-2 contract asserts a contract nobody wrote, and would
    pass a record whose author meant something else entirely.
    """
    bad = []
    for version in (3, 4, 99, 0, -1):
        rec = _deep()
        rec["schema_version"] = version
        bad += expect_controlled_red(f"schema_version = {version}", rec,
                                     "schema_version")
    # ...and the two it does define must still work, or this is over-tightening.
    if not audit_dict(_deep()).ok:
        bad.append("schema 2 stopped passing")
    return bad


def the_identity_fields_must_be_strings() -> list[str]:
    """Seven required fields that were never required to be strings.

    These bind the record to a card, a revision, a physical sample, a reader, a
    moment and a machine. A record whose SKU is `null` or `{}` binds nothing,
    and it is exactly what a later qualification would cite.
    """
    bad = []
    wrong = ({"a": 1}, [1, 2], 7, True, None, 12.5, ["h"])
    for field, value in zip(aud.S2_IDENTITY_FIELDS, wrong):
        rec = _deep()
        rec[field] = value
        bad += expect_controlled_red(f"{field} = {value!r}", rec, field)
    if len(aud.S2_IDENTITY_FIELDS) != 7:
        bad.append(f"{len(aud.S2_IDENTITY_FIELDS)} identity fields; the seven "
                   f"named by the finding are sku, revision, cid, sample, "
                   f"reader, measured_at and host")
    return bad


def an_empty_identity_binds_nothing() -> list[str]:
    """PM's P1-R24 direction, not the verifier's finding.

    P1-R23-V01 explicitly left nonempty-after-trimming as an open PM/WP-05
    policy question. The assignment decides it, following WP-05's existing
    identity/result binding, so it is enforced here -- and recorded as a policy
    call rather than a verifier requirement, because the two are not the same
    kind of thing and a later round should be able to tell them apart.
    """
    bad = []
    for field in aud.S2_IDENTITY_FIELDS:
        for blank in ("", "   ", "\t\n"):
            rec = _deep()
            rec[field] = blank
            bad += expect_controlled_red(f"{field} = {blank!r}", rec, field)
    return bad


def the_top_level_value_must_be_an_object() -> list[str]:
    """A list is valid JSON and is not a record.

    Everything downstream membership-tests and indexes it; reaching `"x" in rec`
    with an int raises rather than reports.
    """
    bad = []
    for payload in ([1, 2, 3], "a string", 42, 3.5, True, None, []):
        try:
            a = _json_audit(payload)
        except Exception as exc:                          # noqa: BLE001
            bad.append(f"top-level {type(payload).__name__} raised "
                       f"{type(exc).__name__}: {exc}")
            continue
        if a.ok:
            bad.append(f"top-level {payload!r} was audited as a record")
        elif not any("top-level JSON value" in p for p in a.problems):
            bad.append(f"top-level {type(payload).__name__} failed without "
                       f"naming the shape: {a.problems}")
    return bad


def the_writer_refuses_before_it_opens_the_target() -> list[str]:
    """The refusal has to come BEFORE the card is touched, not after.

    A run that cannot be bound to a card is not worth the card's write
    endurance. Refusing afterwards means the operator has spent a session
    producing a record the auditor will reject.
    """
    bad = []
    if not msw.identity_problems({}):
        bad.append("a record with no identity at all was accepted by the writer")
    for flag, key, _what in msw.REQUIRED_IDENTITY:
        full = {k: "x" for _f, k, _w in msw.REQUIRED_IDENTITY}
        for blank in (None, "", "  "):
            probe = dict(full)
            probe[key] = blank
            problems = msw.identity_problems(probe)
            if not problems:
                bad.append(f"the writer accepted {key}={blank!r}")
            elif not any(flag in p for p in problems):
                bad.append(f"the writer's refusal for {key} does not name "
                           f"{flag}: {problems}")
        if msw.identity_problems(full):
            bad.append(f"a complete identity was refused: "
                       f"{msw.identity_problems(full)}")

    # End to end: run the real CLI against a real directory and prove it wrote
    # nothing. Checking the function in isolation would not catch a refusal
    # placed after the first write.
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run(
            [sys.executable, str(Path(msw.__file__).resolve()), d],
            capture_output=True, text=True)
        if r.returncode == 0:
            bad.append("the writer exited 0 with no identity supplied")
        leftovers = sorted(p.name for p in Path(d).iterdir())
        if leftovers:
            bad.append(f"the writer touched the target before refusing: "
                       f"{leftovers}")
        if "--sku is required" not in r.stderr:
            bad.append(f"the refusal does not name the missing flag: "
                       f"{r.stderr[:200]}")
    return bad


def the_p1_r23_controls_stay_specific_under_noise() -> list[str]:
    """One red condition must not mask another.

    Every case above is injected a second time alongside an unrelated, always-
    failing defect. If the targeted message disappears, the control was only
    ever firing because the record was broken in general.
    """
    bad = []
    cases = [
        ("bytes_per_mb", lambda r: r.__setitem__("bytes_per_mb", 0)),
        ("total_bytes", lambda r: r["space_after_measurement"].__setitem__(
            "total_bytes", 0)),
        ("schema_version", lambda r: r.__setitem__("schema_version", "bogus")),
        ("schema_version", lambda r: r.__setitem__("schema_version", 3)),
    ] + [(f, (lambda f=f: (lambda r: r.__setitem__(f, None)))())
         for f in aud.S2_IDENTITY_FIELDS]
    for marker, mutate in cases:
        rec = _deep()
        mutate(rec)
        rec["windows"][-1]["fsync_ok"] = False        # unrelated, always fails
        rec["windows"][-1]["sync_error"] = "injected unrelated failure"
        try:
            a = audit_dict(rec)
        except Exception as exc:                      # noqa: BLE001
            bad.append(f"{marker} raised under noise: {type(exc).__name__}")
            continue
        if not any(marker in p for p in a.problems):
            bad.append(f"{marker}'s failure vanished when an unrelated one was "
                       f"present: {a.problems}")
    return bad


CONTROLS = (
    the_good_fixture_passes,
    short_writes_are_looped_not_assumed,
    a_stalled_write_raises_rather_than_spins,
    the_schema_is_closed,
    a_false_summary_is_rejected_not_ignored,
    an_invented_target_kind_cannot_evade_the_size_branch,
    the_write_trace_is_proven_not_believed,
    window_order_and_offsets_are_enforced,
    timing_and_the_closing_flush_are_enforced,
    totals_and_final_size_are_enforced,
    capacity_accounting_is_enforced,
    the_controls_stay_specific_under_noise,
    summary_tampering_is_caught_in_legacy_records,
    every_adjacent_pair_is_what_is_computed,
    an_unreadable_record_fails,
    the_closing_flush_interval_must_run_forwards,
    the_closing_flush_object_is_closed,
    a_malformed_timestamp_is_reported_not_raised,
    a_boolean_is_not_an_integer_identity,
    an_integral_float_is_not_an_integer_byte_count,
    the_declared_window_size_must_match_the_windows,
    the_declared_criteria_must_be_the_methods,
    the_nested_capacity_objects_are_closed,
    a_figure_that_cannot_be_measured_must_be_null,
    an_honest_raw_device_record_still_passes,
    every_p1_r21_form_is_covered_and_none_of_them_crash,
    a_denominator_is_checked_before_it_divides,
    the_declared_version_is_not_coerced,
    an_undefined_schema_version_is_not_audited_as_schema_2,
    the_identity_fields_must_be_strings,
    an_empty_identity_binds_nothing,
    the_top_level_value_must_be_an_object,
    the_writer_refuses_before_it_opens_the_target,
    the_p1_r23_controls_stay_specific_under_noise,
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
    nested = (len(aud.S2_FSYNC_REQUIRED) + len(aud.S2_FILL_REQUIRED)
              + len(aud.S2_SPACE_REQUIRED) + len(aud.S2_WINDOW_REQUIRED)
              + len(aud.S2_CALL_REQUIRED))
    print(f"OK  sustained-write: {len(CONTROLS)} retained controls pass over "
          f"{len(aud.S2_REQUIRED)} required schema-2 fields and {nested} "
          f"nested ones; the write-call trace, window order and offsets, "
          f"timing and the closing flush, totals and final size, capacity "
          f"accounting, target branch, schema closure, false summaries and "
          f"legacy tampering all go red, and every P1-R21-V01 malformed form "
          f"is rejected by report rather than by traceback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
