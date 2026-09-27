#!/usr/bin/env python3
"""Replay a Product adapter's JSONL evidence against the frozen WP-06 oracle."""
import argparse
import hashlib
import json
from pathlib import Path

from oracle import cases, check, digest_plan


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replay(path):
    by_id = {}
    for line in Path(path).read_text().splitlines():
        obj = json.loads(line)
        key = obj.get("case")
        if key in by_id:
            raise AssertionError("duplicate case " + str(key))
        by_id[key] = obj
    expected = {c.id: c for c in cases()}
    if set(by_id) != set(expected):
        raise AssertionError("case census mismatch: missing=%s extra=%s" %
                             (sorted(set(expected) - set(by_id)), sorted(set(by_id) - set(expected))))
    failures = {}
    for key, case in expected.items():
        try:
            check(case, by_id[key])
        except (AssertionError, KeyError, TypeError, ValueError, OverflowError) as e:
            failures[key] = str(e)
    return failures


def main():
    p = argparse.ArgumentParser()
    p.add_argument("observations", type=Path)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--adapter-kind", choices=("product", "synthetic"), required=True)
    p.add_argument("--adapter-source-sha", required=True)
    p.add_argument("--product-commit", required=True)
    p.add_argument("--product-tree", required=True)
    a = p.parse_args()
    failures = replay(a.observations)
    result = {"schema": "wp06-r44-manifest-v1", "passed": not failures,
              "case_count": len(cases()), "plan_sha256": digest_plan(),
              "observations_sha256": sha(a.observations), "oracle_sha256": sha(__file__.replace("runner.py", "oracle.py")),
              "adapter_kind": a.adapter_kind, "adapter_source_sha256": a.adapter_source_sha,
              "product_commit": a.product_commit, "product_tree": a.product_tree, "failures": failures}
    if a.manifest.exists():
        raise SystemExit("refusing to overwrite manifest")
    a.manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(("PASS" if not failures else "FAIL"), len(cases()), "cases", len(failures), "failures")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
