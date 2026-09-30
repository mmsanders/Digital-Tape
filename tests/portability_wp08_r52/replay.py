#!/usr/bin/env python3
"""Offline replay of the two-toolchain evidence directory."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from oracle import SPEC_HASHES, observations_sha256, parse_jsonl
from toolchains import FLAGS, digest
from vectors import plan_sha256, vectors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    directory = args.evidence
    manifest = json.loads((directory / "manifest.json").read_text())
    gcc_packed = (directory / "gcc.jsonl.gz").read_bytes()
    clang_packed = (directory / "clang.jsonl.gz").read_bytes()
    gcc_raw, clang_raw = gzip.decompress(gcc_packed), gzip.decompress(clang_packed)
    if gcc_raw != clang_raw:
        raise AssertionError("cross-toolchain public evidence diverged")
    records = parse_jsonl(gcc_raw)
    planned = json.loads((directory / "plan.json").read_text())
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"))
    if canonical(planned) != canonical([vector.public() for vector in vectors()]):
        raise AssertionError("plan file differs from executable plan")
    here = Path(__file__).resolve().parent
    expected = {
        "case_count": len(vectors()),
        "plan_sha256": plan_sha256(),
        "spec_sha256": SPEC_HASHES,
        "observations_sha256": observations_sha256(gcc_raw),
        "gcc_gzip_sha256": hashlib.sha256(gcc_packed).hexdigest(),
        "clang_gzip_sha256": hashlib.sha256(clang_packed).hexdigest(),
        "adapter_sha256": digest(here / "reference_adapter.c"),
        "byte_identical_observations": True,
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise AssertionError("manifest binding")
    if manifest.get("schema") != "wp08-portability-r52-manifest-v1" or \
            manifest.get("verdict") != "PASS" or manifest.get("red_controls_killed", 0) < 12:
        raise AssertionError("manifest verdict/controls")
    for family in ("gcc", "clang"):
        identity = manifest.get(family, {}).get("identity", "")
        if family not in identity.lower() or manifest[family].get("flags") != list(FLAGS):
            raise AssertionError(f"{family} identity/flags")
    print("PASS", len(records), "vectors; byte-identical GCC/Clang;",
          manifest["red_controls_killed"], "red controls")


if __name__ == "__main__":
    main()
