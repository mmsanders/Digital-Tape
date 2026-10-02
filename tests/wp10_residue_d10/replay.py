#!/usr/bin/env python3
"""Offline replay of JSONL evidence (plain, gzip, or '-' for stdin) against a non-overwriting manifest.

The full synthetic stream is ~16.9M injections and is regenerated, not committed:
    python3 synthetic_adapter.py | python3 replay.py - --manifest evidence/synthetic/manifest.json \
        --adapter-kind synthetic --adapter-source-sha <sha256 of LF-normalised synthetic_adapter.py>
The manifest binds the SHA-256 of the uncompressed LF-terminated stream.
"""
import argparse
import gzip
import hashlib
import io
import json
import sys
from pathlib import Path

import plan as P
from oracle import check_stream


def open_stream(path):
    if path == "-":
        return io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", newline="\n")
    raw = Path(path).open("rb")
    if raw.read(2) == b"\x1f\x8b":
        raw.close()
        return gzip.open(path, "rt", encoding="utf-8", newline="\n")
    raw.close()
    return open(path, "r", encoding="utf-8", newline="\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("evidence")
    p.add_argument("--manifest", required=True)
    p.add_argument("--adapter-kind", choices=("synthetic", "product"), required=True)
    p.add_argument("--adapter-source-sha", required=True)
    p.add_argument("--product-commit")
    p.add_argument("--product-tree")
    args = p.parse_args()
    if args.adapter_kind == "product" and not (args.product_commit and args.product_tree):
        p.error("Product replay requires immutable commit and tree")
    h = hashlib.sha256()

    def lines():
        with open_stream(args.evidence) as f:
            for line in f:
                line = line.rstrip("\n")
                if line.strip():
                    h.update(line.encode("utf-8") + b"\n")
                    yield line

    groups, injections, oracle = check_stream(lines())
    census = P.census()
    assert injections == census["injections_total"], (injections, census["injections_total"])
    reached = {f"{r}.{o}.{ph}": sorted(v) for (r, o, ph), v in sorted(oracle.reached.items())}
    record = {"schema": "wp10-residue-d10-manifest-v1", "group_count": groups,
              "groups": census["groups"], "injections": census["injections"],
              "injections_total": census["injections_total"], "closure_reruns": census["closure_reruns"],
              "caseset_sha256": census["caseset_sha256"], "stream_sha256": h.hexdigest(),
              "outcomes_reached": reached, "adapter_kind": args.adapter_kind,
              "adapter_source_sha256": args.adapter_source_sha,
              "product_commit": args.product_commit, "product_tree": args.product_tree}
    manifest = Path(args.manifest)
    if manifest.exists():
        actual = json.loads(manifest.read_bytes().decode("utf-8"))
        diff = {k for k in record if actual.get(k) != record[k]}
        assert not diff, f"manifest binding mismatch: {sorted(diff)}"
    else:
        manifest.write_bytes((json.dumps(record, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    print(f"PASS {groups} groups, {injections} injections, {census['closure_reruns']} closure re-runs; "
          f"stream {record['stream_sha256']}")


if __name__ == "__main__":
    main()
