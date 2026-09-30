#!/usr/bin/env python3
"""Offline replay for synthetic or separately produced Product observations."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from oracle import SPEC_HASHES, cases, check, plan_digest


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    packed = path.read_bytes()
    raw = gzip.decompress(packed) if path.suffix == ".gz" else packed
    records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    return packed, raw, records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--adapter-kind", required=True, choices=("synthetic", "product"))
    parser.add_argument("--adapter-source-sha256", required=True)
    parser.add_argument("--product-commit")
    parser.add_argument("--product-tree")
    args = parser.parse_args()
    if args.manifest.exists():
        raise SystemExit("refusing to overwrite manifest")
    if args.adapter_kind == "product" and not (args.product_commit and args.product_tree):
        raise SystemExit("Product replay requires exact Product commit and tree")
    if len(args.adapter_source_sha256) != 64:
        raise SystemExit("adapter source SHA-256 must be 64 hex characters")

    packed, raw, records = load(args.evidence)
    expected_cases = cases()
    if len(records) != len(expected_cases):
        raise AssertionError("evidence case census")
    if [record.get("case") for record in records] != [case.id for case in expected_cases]:
        raise AssertionError("evidence plan order or identity")
    if len({record["case"] for record in records}) != len(records):
        raise AssertionError("duplicate evidence case")
    for case, record in zip(expected_cases, records):
        check(case, record)

    here = Path(__file__).resolve().parent
    manifest = {
        "schema": "wp09-capacity-r52-manifest-v1",
        "verdict": "PASS",
        "scope": "offline observation replay; not Product acceptance unless adapter_kind=product",
        "adapter_kind": args.adapter_kind,
        "adapter_source_sha256": args.adapter_source_sha256,
        "product_commit": args.product_commit,
        "product_tree": args.product_tree,
        "case_count": len(records),
        "plan_sha256": plan_digest(),
        "spec_sha256": SPEC_HASHES,
        "evidence_file": args.evidence.name,
        "evidence_file_sha256": hashlib.sha256(packed).hexdigest(),
        "observations_sha256": hashlib.sha256(raw).hexdigest(),
        "oracle_sha256": sha(here / "oracle.py"),
        "replay_sha256": sha(Path(__file__).resolve()),
    }
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("PASS", json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
