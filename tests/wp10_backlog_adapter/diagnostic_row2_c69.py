#!/usr/bin/env python3
"""Row-2 C69 plan finding: diagnostic. NOT the canonical run, and not evidence.

The canonical verdict is replay.py over the retained stream (run_product.py).
It fails at the first C69 row-2 case: oracle.check_row2 binds each observation
to sha256(canonical(C69.oracle.expected_snapshot(case, C69.oracle._fixture_snapshot(case)))),
the whole expected compact-snapshot object. That object carries two summary
fields the accepted C69 campaign oracle never binds:

  image_sha256  - the model copies the *pre-operation* image digest forward
                  unchanged, so it cannot equal the digest of any post-crash
                  image whose metadata changed;
  chunk_sha256  - taken from the pristine fixture, so for record_commit it
                  omits the audio chunk the case's own setup writes before the
                  crash scope (the accepted oracle compares chunk digests to the
                  *observed* pre-snapshot instead).

This script re-runs every planned C69 row-2 case through the same worker and,
per case, reports what the accepted C69 oracle itself compares:

  metadata_equal    Product post-crash superblocks and index slots == the row-2
                    model's (the fixture-based object check_row2 hashes)
  campaign_equal    C69.oracle._raw_parts(post) == _raw_parts(expected_snapshot(case,
                    observed pre)): exactly the accepted campaign's byte comparison
  chunks_as_pre     Product chunk digests == its own pre-snapshot (the accepted
                    campaign's require_chunk_hashes_equal)
  free_chunks_ok    remount free_chunks == total_chunks - frontier, the row-2
                    assertion, computed exactly as oracle.c69_expectation does
  differing_fields  which top-level snapshot fields differ from the model object

It exits 0 only if, for every case, the first four hold and the only differing
fields are a subset of {image_sha256, chunk_sha256}.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_product as rp  # noqa: E402  plan, fixtures and worker protocol; no verdicts

C = rp.C
SUMMARY = {"image_sha256", "chunk_sha256"}


def frontier_free(post: dict, side: str):
    st = C.media.inspect_snapshot(post, requested_side=side)
    if st["mount_result"] != "TAPE_OK":
        return st["mount_result"], None
    sb = st["superblock"]["selected"]
    live_b = None if st["degraded_b"] else st["side_b"]["selected"]["entries"]
    high = sb["a_high_water"]
    front = high if live_b is None else max([high] + [f + (s + n - 1) // C.fixture.CHUNK_FRAMES + 1
                                                      for f, s, n in live_b])
    return "TAPE_OK", C.fixture.TOTAL_CHUNKS - front


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True, help="report JSON path")
    a = ap.parse_args()
    cases = list(rp.c69_cases())
    stats: collections.Counter = collections.Counter()
    bad = []
    with tempfile.TemporaryDirectory(prefix="wp10b-diag-") as t:
        tmp = Path(t)
        proc = subprocess.Popen([str(rp.BUILD / "wp10b_c69_worker"), *rp.c69_fixtures(tmp)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        assert proc.stdin is not None and proc.stdout is not None
        seen = set()
        for case in cases:
            key = (case["scope"], case["family"], case["variant"], case.get("seed"))
            if key not in seen:
                proc.stdin.write("\t".join(["B", case["family"], case["variant"], case.get("seed", "-")]) + "\n")
                proc.stdin.flush()
                proc.stdout.readline()
                seen.add(key)
            inj = case["injection"]
            ordinal = inj["flush_ordinal"] if "flush_ordinal" in inj else inj["write_ordinal"]
            landed = 0 if "flush_ordinal" in inj else inj["landed_bytes"]
            proc.stdin.write("\t".join(["C", str(case["case_index"]), case["scope"], case["family"],
                                        case["variant"], case["mode"], inj["kind"], str(ordinal), str(landed),
                                        case.get("seed", "-")]) + "\n")
            proc.stdin.flush()
            o = json.loads(proc.stdout.readline())
            post, pre = o["post_snapshot"], o["pre_snapshot"]
            model = C.oracle.expected_snapshot(case, C.oracle._fixture_snapshot(case))
            side = o["remount_side"]
            result, free = frontier_free(model, side)
            meta = ("primary_hex", "mirror_hex", "slots")
            facts = {
                "metadata_equal": all(post.get(k) == model.get(k) for k in meta),
                "campaign_equal": C.oracle._raw_parts(post)
                                  == C.oracle._raw_parts(C.oracle.expected_snapshot(case, pre)),
                "chunks_as_pre": post.get("chunk_sha256") == pre.get("chunk_sha256"),
                "free_chunks_ok": o["actual_remount_result"] == result
                                  and o.get("remount_free_chunks") == free,
            }
            differing = tuple(sorted(k for k in set(post) | set(model) if post.get(k) != model.get(k)))
            stats[(case["family"], case["variant"], differing, *facts.values())] += 1
            if not all(facts.values()) or not set(differing) <= SUMMARY:
                bad.append({"case_index": case["case_index"], **facts, "differing": list(differing)})
        proc.stdin.write("D\n")
        proc.stdin.close()
        proc.wait()
    report = {
        "canonical": False,
        "cases": len(cases),
        "by_family": [{"family": k[0], "variant": k[1], "differing_fields": list(k[2]),
                       "metadata_equal": k[3], "campaign_equal": k[4], "chunks_as_pre": k[5],
                       "free_chunks_ok": k[6], "cases": v}
                      for k, v in sorted(stats.items())],
        "cases_outside_the_finding": bad[:50],
        "cases_outside_the_finding_count": len(bad),
    }
    a.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", newline="\n")
    for row in report["by_family"]:
        print(row)
    print(f"{len(cases)} C69 row-2 cases; {len(bad)} outside the summary-field finding")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
