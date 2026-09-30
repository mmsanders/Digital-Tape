#!/usr/bin/env python3
"""Positive synthetic census and one causal red control per missing row."""
from __future__ import annotations

import copy

from oracle import check_all, load_plan, plan_sha256
from synthetic_adapter import all_observations


def mutate(obs, variant=None):
    cid = obs["case"]
    if cid == "E-SIDEA-REFUSE":
        obs["events"].append({"step":"exercise","op":"write","ordinal":1,"lba":0})
    elif cid == "E-RESPOOL-FULL":
        obs["calls"][-1]["result"] = "TAPE_OK"
    elif cid == "E-RECORD-PROMOTE":
        obs["snapshots"]["after_promote"]["A1"] = obs["snapshots"]["before"]["A1"]
    elif cid == "F-STAGE-DEGRADED-ABSENT":
        obs["calls"][-1]["result"] = "TAPE_ERR_NO_VALID_INDEX"
    elif cid == "F-STAGE-DEGRADED-DIVERGENT":
        obs["snapshots"]["after_remount"] = copy.deepcopy(obs["snapshots"]["before"])
    elif cid.startswith("F-LIVEB-"):
        chunk_writes = [e for e in obs["events"] if e["op"] == "write" and e.get("count") == 1024]
        if variant == "below_floor":
            # the old failure: phase-1 / pass-1 allocation one chunk below the live-B floor (5)
            chunk_writes[0]["lba"] = 2048 + 4 * 1024
        elif variant == "below_floor_unreferenced":
            # below the floor but not live (chunk 1, under a_high_water): only rule (a) can catch it
            chunk_writes[0]["lba"] = 2048 + 1 * 1024
        elif variant == "second_phase_shape":
            # disjoint but wrong second-phase destination: promote [1,4) not [0,3); re-spool below H
            chunk_writes[3]["lba"] = 2048 + (3 if "PROMOTE" in cid else 1) * 1024
        else:
            # a second-phase write into the then-live phase-1 / pass-1 run at chunk 5
            chunk_writes[3]["lba"] = 2048 + 5 * 1024


def main():
    clean = all_observations()
    count = check_all(clean)
    killed = 0
    for i in range(len(clean)):
        variants = ("below_floor", "below_floor_unreferenced", "second_phase_live", "second_phase_shape") if clean[i]["case"].startswith("F-LIVEB-") else (None,)
        for variant in variants:
            bad = copy.deepcopy(clean)
            mutate(bad[i], variant)
            try:
                check_all(bad)
            except AssertionError:
                killed += 1
            else:
                raise AssertionError(f"red control survived: {bad[i]['case']} {variant}")
    assert count == len(load_plan()["cases"]) and killed == count + 6
    print(f"PASS {count} positive synthetic cases; {killed} row-specific red controls killed; plan {plan_sha256()}")


if __name__ == "__main__":
    main()
