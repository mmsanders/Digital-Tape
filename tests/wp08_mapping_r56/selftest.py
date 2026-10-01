#!/usr/bin/env python3
"""WP-08 mapped-run self-test: fixture, census, clean synthetic run, causal controls on exact kill sets.

Each control's kill set is derived from the fixture's mapping, not from the oracle: a row-1 case must go red
exactly when one of the four frames it renders is mapped differently by the mutant; row 2 renders the whole
side, so it goes red whenever any frame of that side is.
"""
from __future__ import annotations

import oracle as O
import rows as R
from synthetic_adapter import MUTANTS, lines, observation

EXPECTED = {"row1": 60, "row2": 2}
KILL_COUNTS = {"ignore_start_frame": 62, "chunk_crossing_wraps": 21, "sort_entries_by_physical": 62,
               "side_a_plays_b_index": 31, "reverse_crossing_stale": 6, "render_reads_device": 62}
N = R.N


def mapped(entries, t, start_zero=False, wrap=False):
    for (first, start, n), s in zip(entries, R.run_starts(entries)):
        if s <= t < s + n:
            p = (0 if start_zero else start) + (t - s)
            return (first, p % N) if wrap else (first + p // N, p % N)


def affected(mutant, side):
    """Timeline frames of `side` whose bytes the mutant changes, or None when the mutant is not a mapping one."""
    es = R.SIDES[side]["entries"]
    if mutant == "ignore_start_frame":
        alt = lambda t: mapped(es, t, start_zero=True)
    elif mutant == "chunk_crossing_wraps":
        alt = lambda t: mapped(es, t, wrap=True)
    elif mutant == "sort_entries_by_physical":
        alt = lambda t: mapped(sorted(es, key=lambda e: e[0] * N + e[1]), t)
    elif mutant == "side_a_plays_b_index":
        alt = lambda t: mapped(R.SIDES["B"]["entries"] if side == "A" else es, t)
    else:
        return None
    return {t for t in range(R.TOTAL) if alt(t) != mapped(es, t)}


def window(case):
    if case["row"] == 2:
        return set(range(R.TOTAL))
    d = 1 if case["rate"] > 0 else -1
    return {case["seek"] + d * k for k in range(R.ROW1_RENDER)}


def expected_kills(mutant):
    out = set()
    for case in O.iter_cases():
        hit = affected(mutant, case["side"])
        if hit is not None:
            if hit & window(case):
                out.add(case["index"])
        elif mutant == "render_reads_device":
            out.add(case["index"])
        elif mutant == "reverse_crossing_stale":
            # Stale only when reverse play steps from the first frame of a run's later chunk into the earlier
            # one AFTER having emitted that first frame: seek on or one past the crossing, or the full traversal.
            es = R.SIDES[case["side"]]["entries"]
            inner = {t for t in range(1, R.TOTAL) if mapped(es, t)[0] != mapped(es, t - 1)[0]
                     and any(s < t < s + n for (_, _, n), s in zip(es, R.run_starts(es)))}
            if case["row"] == 2 or (case["rate"] < 0 and any(case["seek"] >= t and case["seek"] - 3 <= t - 1
                                                           for t in inner)):
                out.add(case["index"])
    return out


def main():
    img = R.image()
    for v in R.SIDES.values():
        lba = R.FINAL.SLOT_LBA[v["slot"]]
        slot = R.FINAL.parse_slot(img[lba * R.BLOCK:(lba + 2) * R.BLOCK])
        assert slot == {"sequence": v["sequence"], "side": v["side"], "entries": list(v["entries"])}, slot
    census = O.plan_census()
    for k, v in EXPECTED.items():
        assert census[k] == v, f"census {k}: {census[k]} != {v}"
    n = O.check_stream(lines())
    killed = {}
    for mutant in MUTANTS:
        reds = set()
        for case in O.iter_cases():
            try:
                O.check(case, observation(case, mutant))
            except AssertionError:
                reds.add(case["index"])
        want = expected_kills(mutant)
        assert reds == want, f"control {mutant} killed {sorted(reds)} expected {sorted(want)}"
        assert len(reds) == KILL_COUNTS[mutant], f"control {mutant}: {len(reds)} != {KILL_COUNTS[mutant]}"
        killed[mutant] = len(reds)
    print(f"PASS census {census}; clean synthetic {n}/{n}; {len(MUTANTS)} controls killed on exact sets: "
          + ", ".join(f"{m}={k}" for m, k in killed.items()))


if __name__ == "__main__":
    main()
