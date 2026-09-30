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
        count, findings = check_stream(line for line in f if line.strip())
    census = plan_census()
    record = {"schema": "wp10-r53-manifest-v1", "case_count": count,
              "crash_cases": census["crash"], "caseset_sha256": census["caseset_sha256"],
              "by_mode": census["by_mode"], "evidence_sha256": digest(args.evidence),
              "findings": findings, "adapter_kind": args.adapter_kind,
              "adapter_source_sha256": args.adapter_source_sha,
              "product_commit": args.product_commit, "product_tree": args.product_tree}
    manifest = Path(args.manifest)
    if manifest.exists():
        actual = json.loads(manifest.read_text())
        diff = {k for k in record if actual.get(k) != record[k]}
        assert not diff, f"manifest binding mismatch: {sorted(diff)}"
    else:
        manifest.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", newline="\n")
    print(f"PASS {count} observations ({census['crash']} exhaustive crash injections, "
          f"{census['by_mode']}); evidence {record['evidence_sha256']}; findings {findings}")


if __name__ == "__main__":
    main()
