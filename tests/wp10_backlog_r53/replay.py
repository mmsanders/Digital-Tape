#!/usr/bin/env python3
"""Offline replay of gzip JSONL evidence against a non-overwriting manifest."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from oracle import check_stream, plan_census


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
    with gzip.open(args.evidence, "rt", encoding="utf-8") as f:
        count, row3 = check_stream(line for line in f if line.strip())
    census = plan_census()
    record = {"schema": "wp10-backlog-r53-manifest-v1", "case_count": count, "row3_injections": row3,
              "row1_crash": census["row1_crash"], "row1_by_mode": census["row1_by_mode"],
              "row2_frontier": census["row2_frontier"], "row2_by_campaign": census["row2_by_campaign"],
              "row2_by_mode": census["row2_by_mode"], "caseset_sha256": census["caseset_sha256"],
              "evidence_sha256": digest(args.evidence), "adapter_kind": args.adapter_kind,
              "adapter_source_sha256": args.adapter_source_sha,
              "product_commit": args.product_commit, "product_tree": args.product_tree}
    manifest = Path(args.manifest)
    if manifest.exists():
        actual = json.loads(manifest.read_text(encoding="utf-8"))
        diff = {k for k in record if actual.get(k) != record[k]}
        assert not diff, f"manifest binding mismatch: {sorted(diff)}"
    else:
        manifest.write_bytes((json.dumps(record, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    print(f"PASS {count} observations (row1 {census['row1_crash']} crash, row2 {census['row2_frontier']} frontier, "
          f"row3 {row3} injections); evidence {record['evidence_sha256']}")


if __name__ == "__main__":
    main()
