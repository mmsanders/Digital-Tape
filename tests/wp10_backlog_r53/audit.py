#!/usr/bin/env python3
"""Validate the WP-10 backlog update against the planner and the #105 ledger's nine backlog ids."""
import hashlib
import json
from pathlib import Path

import oracle as O

ROOT = Path(__file__).resolve().parent
FORMER = [
    "WP10.dup.destination_shape.layout_preserving_rejected_c90_to_c60",
    "WP10.universal.free_next_after_every_injection",
    "WP10.session.record_audio_service_writes",
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
    assert [r["id"] for r in pub] == FORMER[:3], "published rows must be exactly former ranks 1-3"
    assert [r["former_rank"] for r in pub] == [1, 2, 3]
    assert [r["id"] for r in back] == FORMER[3:] and [r["rank"] for r in back] == list(range(1, 7))
    assert [r["former_rank"] for r in back] == list(range(4, 10))
    census = O.plan_census()
    assert pub[0]["injection_points"] == {s: n for s, n in (
        (s, sum(1 for c in O.iter_cases() if c["row"] == 1 and c["kind"] == "crash" and c["scenario"] == s))
        for s in O.D.SCENARIOS)}, "row 1 census"
    assert pub[1]["injection_points"] == census["row2_by_campaign"], "row 2 census"
    assert {O.ROW1, O.ROW2, O.ROW3} == {r["id"] for r in pub}
    print("PASS backlog update: published", [r["id"] for r in pub], "| remaining ranked backlog",
          [r["id"] for r in back], "| sha256", hashlib.sha256(raw).hexdigest(),
          "| caseset", census["caseset_sha256"])


if __name__ == "__main__":
    main()
