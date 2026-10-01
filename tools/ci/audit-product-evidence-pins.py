#!/usr/bin/env python3
"""Pin audit for independently accepted Product evidence bundles (V-R54-01, #337).

The current-engine regression gates prove that each accepted binding regenerates
byte-identically to its in-tree retained bundle. This audit closes the other half:
the retained bundle itself is pinned in tests/IMPORTS.json, a Michael-owned
CODEOWNERS path, so a PR cannot change engine/, regenerate, reseal a bundle and its
SHA256SUMS, and stay green.

It fails when:
  - a pinned bundle is missing;
  - a pinned bundle's file set, any file's SHA-256, or its canonical observation
    stream SHA-256 differs from its pin;
  - a directory matching tests/*_adapter/evidence/p1-r*-product exists with
    neither a pin nor an explicit `retained_unaccepted_bundles` entry (which is
    pinned byte-for-byte the same way).

It reads files from the working tree, so it checks exactly what CI built and ran.
A green run is mechanical authentication only: not a disposition and not acceptance.

Usage: audit-product-evidence-pins.py [--root DIR]   (EVIDENCE_MANIFEST overrides the manifest)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

PATTERN = "tests/*_adapter/evidence/p1-r*-product"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stream_sha(d: Path, names: set[str]) -> tuple[str | None, str]:
    """SHA-256 of the canonical observation stream the replay decides on, if its
    bytes are in the tree. Returns (digest or None, which file it came from)."""
    if "observations.jsonl" in names:
        return sha((d / "observations.jsonl").read_bytes()), "observations.jsonl"
    if "observations.jsonl.gz" in names:
        return sha(gzip.decompress((d / "observations.jsonl.gz").read_bytes())), "observations.jsonl.gz"
    if {"gcc.jsonl.gz", "clang.jsonl.gz"} <= names:
        gcc = gzip.decompress((d / "gcc.jsonl.gz").read_bytes())
        clang = gzip.decompress((d / "clang.jsonl.gz").read_bytes())
        return (sha(gcc) if gcc == clang else "gcc/clang streams differ"), "gcc.jsonl.gz = clang.jsonl.gz"
    return None, "stream not in tree (release asset)"


def check_bundle(root: Path, entry: dict, kind: str) -> list[str]:
    path = entry.get("path", "")
    d = root / path
    if not d.is_dir():
        return [f"{kind} bundle {path} is missing"]
    pinned = entry.get("files") or {}
    on_disk = {p.name for p in d.iterdir() if p.is_file()}
    errors = []
    if on_disk != set(pinned):
        errors.append(f"{path}: file set {sorted(on_disk)} != pinned {sorted(pinned)}")
    for name, want in sorted(pinned.items()):
        f = d / name
        if f.is_file() and sha(f.read_bytes()) != want:
            errors.append(f"{path}/{name}: SHA-256 differs from its pin")
    want_stream = entry.get("observations_sha256")
    if want_stream:
        got, src = stream_sha(d, on_disk)
        if got is not None and got != want_stream:
            errors.append(f"{path}: observation stream ({src}) SHA-256 differs from its pin")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    a = ap.parse_args()
    root = a.root.resolve()
    manifest = Path(os.environ.get("EVIDENCE_MANIFEST") or root / "tests/IMPORTS.json")
    m = json.loads(manifest.read_text(encoding="utf-8"))
    pins = m.get("product_evidence_pins", [])
    unaccepted = m.get("retained_unaccepted_bundles", [])

    print("== product evidence pins ==")
    failures = []
    for entry in pins:
        errs = check_bundle(root, entry, "pinned")
        failures += errs
        if not errs:
            print(f"  ok    [pin] {entry['path']} == {len(entry['files'])} files, stream "
                  f"{(entry.get('observations_sha256') or '-')[:12]}  [{entry.get('verification')}]")
    for entry in unaccepted:
        errs = check_bundle(root, entry, "listed unaccepted")
        failures += errs
        if not errs:
            print(f"  ok    [unaccepted] {entry['path']} unchanged ({entry.get('reason', '')[:60]})")
    known = {e["path"] for e in pins} | {e["path"] for e in unaccepted}
    for d in sorted(root.glob(PATTERN)):
        rel = d.relative_to(root).as_posix()
        if d.is_dir() and rel not in known:
            failures.append(f"{rel} is a retained Product bundle with no pin in tests/IMPORTS.json")
    for f in failures:
        print(f"  FAIL  [pin] {f}")
    print(f"== product evidence pins: {'FAIL' if failures else 'PASS'} "
          f"({len(pins)} pinned, {len(unaccepted)} listed unaccepted, {len(failures)} failed) ==")
    print("   Mechanical authentication only: not a disposition and not acceptance.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
