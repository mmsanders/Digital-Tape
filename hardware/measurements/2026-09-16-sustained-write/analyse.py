#!/usr/bin/env python3
"""Derivation for the 16 September 2026 sustained-write session.

`measurements/TEMPLATE.md` section 6 requires that the arithmetic turning raw
readings into reported numbers be shown, and that any script doing it live in
this repository. This is that script.

It no longer does the arithmetic itself. Every figure comes from
`characterisation/audit_sustained_write.py`, the shared auditor, so the record
and any future run are derived by the same code -- and that code recomputes
from primitives and refuses to trust a stored summary field. Running it on
these five files therefore does two jobs at once: it reproduces the table in
README.md, and it re-audits the raw files for internal consistency.

These five files are **schema 1**: rounded per-window rates and summary fields,
with no byte counts, timestamps, final size or measured occupancy. Their
arithmetic is checkable and was independently reproduced by Verification
(P1-R17-V). Their physical conditions are not checkable after the fact, so this
record is **not complete WP-05 A-2 evidence** and the auditor says so on every
run. Schema 2 retains what is missing; the five submitted files are immutable
and are not migrated.

    python3 analyse.py            exit 1 if any record fails its audit
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "characterisation"))

import audit_sustained_write as aud                      # noqa: E402

RAW = HERE / "raw"
ORDER = ["onn-v10", "pny1", "pny2", "pny3", "pny3-filled"]
FILLED = {"pny3-filled"}


def main() -> int:
    audits = {}
    for name in ORDER:
        p = RAW / f"{name}.json"
        if not p.exists():
            print(f"FAIL missing raw file: {p}", file=sys.stderr)
            return 1
        audits[name] = aud.audit(p)

    print("Derived from the recorded vectors by characterisation/"
          "audit_sustained_write.py.")
    print("Schema 1: summary-only. NOT complete WP-05 A-2 evidence -- see "
          "README.md section 1.\n")

    hdr = (f"{'run':13} {'fill':5} {'worst':>7} {'median':>7} {'best':>7} "
           f"{'pair(all)':>9} {'screen':>7}")
    print(hdr)
    print("-" * len(hdr))
    for name in ORDER:
        d = audits[name].derived
        print(f"{name:13} {'0.8' if name in FILLED else '-':5} "
              f"{d['worst']:7.2f} {d['median']:7.2f} {d['best']:7.2f} "
              f"{d['pair_min_sliding']:9.2f} {audits[name].verdict:>7}")

    print("\nHeadroom on the worst window (the A-2 figure):")
    for name in ORDER:
        d = audits[name].derived
        print(f"  {name:13} {d['headroom_c60']:5.2f}x the 21.2 MB/s C-60 "
              f"requirement   {d['headroom_bar']:5.2f}x the 23.3 MB/s screen")

    print("\nAdjacent-pair minimum -- a descriptive statistic, not an A-2 "
          "criterion.")
    print("Every adjacent pair (i, i+1). The fixed phase-0 pairs the schema-1 "
          "analyser\nused are shown beside it: they are a different statistic "
          "and were mislabelled.")
    for name in ORDER:
        d = audits[name].derived
        print(f"  {name:13} every pair {d['pair_min_sliding']:8.5f}   "
              f"fixed phase-0 {d['pair_min_fixed_phase0']:8.5f}")

    # Stated on the worst window -- the figure A-2 is actually judged on.
    # An earlier version of this record quoted 1.0% on a pair-rate MEAN, which
    # is a different and more flattering statistic than the criterion's own.
    unfilled_pny = [n for n in ORDER if n.startswith("pny") and n not in FILLED]
    worsts = [audits[n].derived["worst"] for n in unfilled_pny]
    spread = max(worsts) - min(worsts)
    print(f"\nUnit-to-unit screen, three unfilled PNY samples, on the worst "
          f"window:\n  values {[round(v, 2) for v in worsts]}  "
          f"spread {spread:.2f} MB/s = "
          f"{100 * spread / (sum(worsts)/len(worsts)):.1f}% of mean")

    print("\nA-4 ceiling check -- best window per run (path, not card):")
    tops = [audits[n].derived["best"] for n in ORDER if n.startswith("pny")]
    for name in ORDER:
        print(f"  {name:13} {audits[name].derived['best']:7.2f}")
    same = sum(1 for t in tops if abs(t - max(tops)) < 0.01)
    print(f"  PNY best-window spread {min(tops):.2f}-{max(tops):.2f} "
          f"({100 * (max(tops) - min(tops)) / (sum(tops)/len(tops)):.1f}% of "
          f"mean); {same} runs sit on the identical maximum")

    same_card = audits["pny3"].derived, audits["pny3-filled"].derived
    print(f"\nThe one filled run, same physical card (pny3):")
    print(f"  worst window   {same_card[0]['worst']:6.2f} unfilled -> "
          f"{same_card[1]['worst']:6.2f} filled  "
          f"({same_card[1]['worst'] - same_card[0]['worst']:+.2f})")
    print("  The 0.8 is a FLAG in a schema-1 file, not a measured occupancy.")

    bad = [n for n, a in audits.items() if not a.ok]
    print()
    for n in bad:
        for p in audits[n].problems:
            print(f"FAIL {n}: {p}", file=sys.stderr)
    if bad:
        return 1
    print(f"All {len(ORDER)} records are internally consistent, and all five "
          f"are schema 1 (legacy).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
