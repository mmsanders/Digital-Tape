#!/usr/bin/env python3
"""Strict 33-case JSONL replay and hash-bound manifest."""
import argparse
import hashlib
import json
from pathlib import Path

from oracle import cases, check, digest_plan


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replay(path):
    observations = {}
    for line in Path(path).read_text().splitlines():
        o = json.loads(line)
        key = o.get("case")
        if key in observations:
            raise AssertionError("duplicate case " + str(key))
        observations[key] = o
    plan = {c.id: c for c in cases()}
    if set(observations) != set(plan):
        raise AssertionError("case census mismatch: missing=%s extra=%s" %
                             (sorted(set(plan) - set(observations)), sorted(set(observations) - set(plan))))
    failures = {}
    for key, case in plan.items():
        try:
            check(case, observations[key])
        except (AssertionError, KeyError, TypeError, ValueError) as e:
            failures[key] = str(e)
    return failures


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
    failures = replay(a.evidence)
    manifest = {"schema": "wp08-r44-manifest-v1", "passed": not failures,
                "cases": len(cases()), "failures": failures, "plan_sha256": digest_plan(),
                "evidence_sha256": sha(a.evidence), "oracle_sha256": sha(Path(__file__).with_name("oracle.py")),
                "adapter_kind": a.adapter_kind, "adapter_source_sha256": a.adapter_source_sha,
                "product_commit": a.product_commit, "product_tree": a.product_tree}
    a.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("PASS" if not failures else "FAIL", len(cases()), "cases", len(failures), "failures")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
