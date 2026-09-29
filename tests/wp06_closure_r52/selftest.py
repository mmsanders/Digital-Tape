#!/usr/bin/env python3
"""Positive synthetic census and one causal red control per missing row."""
from __future__ import annotations

import copy

from oracle import check_all, load_plan, plan_sha256
from synthetic_adapter import all_observations


def mutate(obs):
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
    elif cid == "F-LIVEB-PROMOTE-FLOOR":
        obs["events"][0]["lba"] = 2048 + 3*1024
    elif cid == "F-LIVEB-RESPOOL-FLOOR":
        obs["events"][0]["lba"] = 2048 + 3*1024


def main():
    clean = all_observations()
    count = check_all(clean)
    killed = 0
    for i in range(len(clean)):
        bad = copy.deepcopy(clean)
        mutate(bad[i])
        try:
            check_all(bad)
        except AssertionError:
            killed += 1
        else:
            raise AssertionError("red control survived: " + bad[i]["case"])
    assert killed == count == len(load_plan()["cases"])
    print(f"PASS {count} positive synthetic cases; {killed} row-specific red controls killed; plan {plan_sha256()}")


if __name__ == "__main__":
    main()
