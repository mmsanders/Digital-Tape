#!/usr/bin/env python3
"""Derivation for the 16 September 2026 sustained-write session.

`measurements/TEMPLATE.md` §6 requires that the arithmetic turning raw readings
into reported numbers be shown, and that any script doing it live in this
repository. This is that script. It reads only `raw/*.json` -- the untouched
output of `characterisation/measure_sustained_write.py` -- and recomputes every
figure quoted in README.md from the per-window data.

It deliberately recomputes the verdict from `windows_mb_s` rather than trusting
each file's own `verdict` field, so a corrupted or edited summary line cannot
pass unnoticed. Run it with no arguments:

    python3 analyse.py
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

RAW = Path(__file__).resolve().parent / "raw"

# From characterisation/measure_sustained_write.py. Restated here so a drift
# between this derivation and the tool shows up as a mismatch, not silence.
REQUIRED_C60 = 21.2     # 635,040,000 B / 30 s -- the C-60 copy (ADR-018)
REQUIRED_C90 = 31.75    # what a C-90 would need
BAR = 23.3              # 10% over the C-60 requirement
ADR109_C90_BAR = 35.0   # ADR-109's superseded "worst-case >= 35 -> C-90" rule


def pairwise(windows: list[float], window_mb: int) -> list[float]:
    """Effective rate over each ADJACENT PAIR of windows.

    The runs alternate fast/slow with near-perfect regularity. Whatever causes
    that -- fsync landing on the card's fold boundary is the leading candidate
    -- a pair spans one full cycle, so the pair rate is insensitive to where
    the window boundary happens to fall. Harmonic mean by construction: total
    bytes over total time, not the average of two rates.
    """
    out = []
    for i in range(0, len(windows) - 1, 2):
        a, b = windows[i], windows[i + 1]
        out.append(2 * window_mb / (window_mb / a + window_mb / b))
    return out


def split_parity(windows: list[float]) -> tuple[list[float], list[float]]:
    """Separate the fast and slow halves of the alternation."""
    even = windows[0::2]
    odd = windows[1::2]
    return (even, odd) if statistics.mean(even) >= statistics.mean(odd) else (odd, even)


def load() -> list[dict]:
    runs = []
    for p in sorted(RAW.glob("*.json")):
        d = json.load(open(p))
        w = d["windows_mb_s"]
        fast, slow = split_parity(w)
        pairs = pairwise(w, d["window_mb"])
        runs.append({
            "name": p.stem,
            "sku": d["sku"],
            "filled_to": d["filled_to"],
            "reader": d["reader"],
            "measured_at": d["measured_at"],
            "n_windows": len(w),
            "worst": min(w),
            "best": max(w),
            "mean": d["mean_mb_s"],
            "fast_mean": statistics.mean(fast),
            "slow_mean": statistics.mean(slow),
            "pair_min": min(pairs),
            "pair_mean": statistics.mean(pairs),
            "stated_verdict": d["verdict"],
            "recomputed_verdict": "PASS" if min(w) >= BAR else "FAIL",
        })
    return runs


def main() -> int:
    runs = load()
    bad = [r for r in runs if r["stated_verdict"] != r["recomputed_verdict"]]

    print("Recomputed from raw per-window data. Rates in MB/s.\n")
    hdr = (f"{'run':13} {'fill':5} {'worst':>6} {'best':>6} {'mean':>6} "
           f"{'pairmin':>8} {'verdict':>8}")
    print(hdr)
    print("-" * len(hdr))
    for r in runs:
        print(f"{r['name']:13} {str(r['filled_to'] or '-'):5} {r['worst']:6.2f} "
              f"{r['best']:6.2f} {r['mean']:6.2f} {r['pair_min']:8.2f} "
              f"{r['recomputed_verdict']:>8}")

    print(f"\nVerdict agreement with each file's own field: "
          f"{'OK, all 5 agree' if not bad else 'MISMATCH: ' + str(bad)}")

    print("\nMargin against each requirement (worst 64 MB window):")
    for r in runs:
        print(f"  {r['name']:13} C-60 req {r['worst']/REQUIRED_C60:5.2f}x   "
              f"bar {r['worst']/BAR:5.2f}x   C-90 req {r['worst']/REQUIRED_C90:5.2f}x   "
              f"ADR-109 C-90 bar {r['worst']/ADR109_C90_BAR:5.2f}x")

    print("\nThe alternation, and what survives it:")
    for r in runs:
        print(f"  {r['name']:13} fast {r['fast_mean']:6.2f}  slow {r['slow_mean']:6.2f}  "
              f"ratio {r['fast_mean']/r['slow_mean']:4.2f}   "
              f"128MB-pair {r['pair_min']:6.2f}-{r['pair_mean']:6.2f}")

    pny = [r for r in runs if r["sku"].startswith("pny")]
    unfilled = [r for r in pny if not r["filled_to"]]
    print("\nUnit-to-unit consistency, three unfilled PNY samples (128 MB pair rate):")
    means = [r["pair_mean"] for r in unfilled]
    print(f"  values {[round(m, 2) for m in means]}  "
          f"spread {max(means)-min(means):.2f} = {100*(max(means)-min(means))/statistics.mean(means):.1f}% of mean")

    print("\nA-4 reader-ceiling check -- best window per run:")
    for r in runs:
        print(f"  {r['name']:13} {r['best']:6.2f}")
    tops = [r["best"] for r in pny]
    print(f"  PNY best-window spread {min(tops):.2f}-{max(tops):.2f} "
          f"({100*(max(tops)-min(tops))/statistics.mean(tops):.1f}% of mean); "
          f"{sum(1 for t in tops if abs(t - max(tops)) < 0.01)} runs sit on the identical maximum")

    fill = next(r for r in pny if r["filled_to"])
    same = next(r for r in pny if r["sku"] == fill["sku"] and not r["filled_to"])
    print(f"\n80% fill, same physical card ({fill['sku']}):")
    print(f"  worst window  {same['worst']:6.2f} empty -> {fill['worst']:6.2f} filled  "
          f"({fill['worst']-same['worst']:+.2f})")
    print(f"  128MB pair    {same['pair_mean']:6.2f} empty -> {fill['pair_mean']:6.2f} filled  "
          f"({fill['pair_mean']-same['pair_mean']:+.2f})")

    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
