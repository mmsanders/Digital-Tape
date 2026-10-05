#!/usr/bin/env python3
"""Verdict for one CI lane aggregate (`cheap`, `regression`, `qualification`).

ci.yml's aggregate job for a lane needs every member job, so its `needs`
context carries each member's result. A lane passes only when every member it
selected succeeded and every member it did not select was skipped. A failed or
cancelled member, an unexpected skip, or a member that ran when it should not
have, turns the lane red. Selection follows the classifier's outputs exactly
(tools/ci/ci_lanes.py), and an empty output, which is what a failed classifier
leaves, means "everything was selected".

Usage, from the aggregate job:
  LANE=regression NEEDS='${{ toJSON(needs) }}' DOCS_ONLY=... QUALIFY=... \
  QUALIFY_JOBS=... tools/ci/lane-verdict.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ci_lanes as L  # noqa: E402


def main() -> int:
    lane = os.environ["LANE"]
    needs = json.loads(os.environ["NEEDS"])
    text = L.WORKFLOW.read_text()
    jobs = L.workflow_jobs(text)
    members = L.lanes(text)[lane]
    missing = [m for m in members if m not in needs]
    if missing:
        print(f"FAIL  lane members absent from needs: {missing}")
        return 1
    results = {m: needs[m]["result"] for m in members}
    upstream = {}
    for m in members:
        up = L.upstream_member(jobs, m, members)
        if up and not L.has_qualify_gate(jobs[m], m) and not L.has_docs_gate(jobs[m]):
            upstream[m] = up
    if lane != "cheap":
        cls = needs.get("changes", {}).get("result", "missing")
        print(f"classifier: {cls}; docs_only={os.environ.get('DOCS_ONLY')!r} "
              f"qualify={os.environ.get('QUALIFY')!r} qualify_jobs={os.environ.get('QUALIFY_JOBS')!r}")
    ok, lines = L.lane_verdict(lane, results, os.environ.get("DOCS_ONLY", ""),
                               os.environ.get("QUALIFY", ""), os.environ.get("QUALIFY_JOBS", ""),
                               upstream)
    print("\n".join(lines))
    ran = sum(r == "success" for r in results.values())
    print(f"== {lane}: {'PASS' if ok else 'FAIL'} ({ran}/{len(results)} ran) ==")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
