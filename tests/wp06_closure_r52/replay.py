#!/usr/bin/env python3
"""Offline replay of gzip JSONL evidence with a non-overwriting manifest."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from oracle import check_all, plan_sha256


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
        observations = [json.loads(line) for line in f if line.strip()]
    count = check_all(observations)
    manifest_path = Path(args.manifest)
    if manifest_path.exists():
        actual = json.loads(manifest_path.read_text())
        assert actual["evidence_sha256"] == digest(args.evidence)
        assert actual["plan_sha256"] == plan_sha256()
        assert actual["adapter_kind"] == args.adapter_kind
        assert actual["adapter_source_sha256"] == args.adapter_source_sha
        assert actual.get("product_commit") == args.product_commit
        assert actual.get("product_tree") == args.product_tree
    else:
        manifest_path.write_text(json.dumps({
            "schema":"wp06-r52-manifest-v1", "case_count":count,
            "evidence_sha256":digest(args.evidence), "plan_sha256":plan_sha256(),
            "adapter_kind":args.adapter_kind, "adapter_source_sha256":args.adapter_source_sha,
            "product_commit":args.product_commit, "product_tree":args.product_tree
        }, sort_keys=True, indent=2) + "\n")
    print(f"PASS {count} observations; evidence {digest(args.evidence)}; plan {plan_sha256()}")


if __name__ == "__main__":
    main()
