#!/usr/bin/env python3
"""Supersession witness: over the full R1/R2 census, count the injections at which the DRAFT-9 rule
(residue classified blank, step 1 skipped: the `skip_residue_zeroing` control) mounts under an identity
other than the fresh one. DRAFT-10 must have zero such injections; replay.py checks that.

Writes evidence/d9_census.json (LF, sorted keys).
"""
import json
from pathlib import Path

import plan as P
from synthetic_adapter import observation


def main():
    by, total, groups_red = {}, 0, 0
    for g in P.iter_groups():
        if g["row"] == "R3":
            continue
        obs = observation(g, "skip_residue_zeroing")
        fresh = "OK." + P.FRESH[g["op"]].hex()[:8]
        bad = sum(1 for e in obs["injections"] if e.split(" ")[1].startswith("OK.") and e.split(" ")[1] != fresh)
        if bad:
            key = f"{g['row']}.{g['op']}.{g['shape']}.{g['mode']}"
            entry = by.setdefault(key, {"groups": 0, "injections": 0, "l1": []})
            entry["groups"] += 1
            entry["injections"] += bad
            if "l1" in g:
                entry["l1"].append(g["l1"])
            total += bad
            groups_red += 1
    for entry in by.values():
        ls = entry.pop("l1")
        if ls:
            entry["l1_min"], entry["l1_max"] = min(ls), max(ls)
    out = {"schema": "wp10-residue-d10-d9-census-v1", "rule": "DRAFT-9 (skip_residue_zeroing)",
           "resurrecting_groups": groups_red, "resurrecting_injections": total, "by_group": by}
    path = Path(__file__).resolve().parent / "evidence" / "d9_census.json"
    path.write_bytes((json.dumps(out, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    print(f"DRAFT-9 rule: {total} resurrecting injections in {groups_red} groups")


if __name__ == "__main__":
    main()
