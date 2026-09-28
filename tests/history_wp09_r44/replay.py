#!/usr/bin/env python3
"""Streaming replay with a non-overwriting, source-bound result manifest."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from oracle import check


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt") as f:
        for line in f:
            yield json.loads(line)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("evidence", type=Path)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--adapter-kind", choices=("product", "synthetic"), required=True)
    p.add_argument("--adapter-source-sha", required=True)
    p.add_argument("--product-commit", required=True)
    p.add_argument("--product-tree", required=True)
    a = p.parse_args()
    if a.manifest.exists():
        raise SystemExit("refusing to overwrite manifest")
    try:
        result = check(iter(lines(a.evidence)))
        failure = None
    except (AssertionError, KeyError, TypeError, ValueError) as e:
        result, failure = None, str(e)
    manifest = {"schema": "wp09-r44-manifest-v1", "adapter_kind": a.adapter_kind,
                "adapter_source_sha256": a.adapter_source_sha,
                "product_commit": a.product_commit, "product_tree": a.product_tree,
                "evidence_bytes": a.evidence.stat().st_size, "evidence_sha256": sha(a.evidence),
                "oracle_sha256": sha(Path(__file__).with_name("oracle.py")),
                "passed": failure is None, "result": result, "failure": failure}
    a.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("PASS" if failure is None else "FAIL", result or failure)
    return failure is not None


if __name__ == "__main__":
    raise SystemExit(main())
