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
        count, row3, findings = check_stream(line for line in f if line.strip())
    census = plan_census()
    record = {"schema": "wp10-final-r54-manifest-v1", "case_count": count, "row1": census["row1"],
              "row2": census["row2"], "row3_groups": census["row3_groups"], "row3_injections": row3,
              "row4": census["row4"], "row4_by_mode": census["row4_by_mode"],
              "caseset_sha256": census["caseset_sha256"], "findings": findings, "evidence_sha256": digest(args.evidence),
              "adapter_kind": args.adapter_kind, "adapter_source_sha256": args.adapter_source_sha,
              "product_commit": args.product_commit, "product_tree": args.product_tree}
    manifest = Path(args.manifest)
    if manifest.exists():
        actual = json.loads(manifest.read_text(encoding="utf-8"))
        diff = {k for k in record if actual.get(k) != record[k]}
        assert not diff, f"manifest binding mismatch: {sorted(diff)}"
    else:
        manifest.write_bytes((json.dumps(record, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    print(f"PASS {count} observations (rows 1-2 {census['row1'] + census['row2']} contract, row3 {row3} "
          f"injections, row4 {census['row4']}); evidence {record['evidence_sha256']}; findings {findings}")


if __name__ == "__main__":
    main()
