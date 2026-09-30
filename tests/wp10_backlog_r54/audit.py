#!/usr/bin/env python3
"""Validate the backlog update against the #110 six-row backlog and the planner census."""
import hashlib
import json
from pathlib import Path

import oracle as O

ROOT = Path(__file__).resolve().parent
FORMER = [
    "WP10.session.load.mount_repair_write",
    "WP10.dup.rerun_completes",
    "WP10.dup.destination_shape.mounts_both_sides_high_label",
    "WP10.counters.v5_015.reset_b_and_stage_clear_generation",
    "WP10.headroom.zero_needed_reserved.empty_respool_each_counter_each_value",
    "WP10.op.respool.post_crash_render",
]


def main():
    raw = (ROOT / "backlog-update.json").read_bytes().replace(b"\r\n", b"\n")
    d = json.loads(raw)
    pub, back = d["published_here"], d["backlog"]
    assert [r["id"] for r in pub] == FORMER[:3] and [r["former_rank"] for r in pub] == [1, 2, 3]
    assert [r["id"] for r in back] == FORMER[3:] and [r["rank"] for r in back] == [1, 2, 3]
    assert [r["former_rank"] for r in back] == [4, 5, 6]
    assert [r["id"] for r in pub] == [O.ROW1, O.ROW2, O.ROW3]
    census = O.plan_census()
    assert pub[0]["injection_points"] == census["row1_by_shape"], "row 1 census"
    assert pub[1]["injection_points"] == census["row2_by_shape"], "row 2 census"
    assert pub[2]["completion_cases"] == census["row3"], "row 3 census"
    print("PASS backlog update: published", [r["id"] for r in pub], "| remaining", [r["id"] for r in back],
          "| sha256", hashlib.sha256(raw).hexdigest(), "| caseset", census["caseset_sha256"])


if __name__ == "__main__":
    main()
