#!/usr/bin/env python3
"""Negative control for the WP-13 DRAFT-9 carry-over check (#359).

CLAUDE.md §1: every new gate needs a real negative control. The DRAFT-9 WP-13
collector now accepts whatever bundle spec/VERSION.md issues, but only while
that bundle's WP-13 acceptance row is byte-identical to DRAFT-9's. This plants
each violation in a scratch copy of spec/ and asserts the check refuses it,
then asserts the unmodified copy and an edit outside the row are accepted.

It reads the repository and writes only to a temporary directory.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "embedded_readiness_adapter"))
import collect_product_evidence_draft9 as c  # noqa: E402

ACC = "spec/acceptance.md"


def scratch(tmp: Path, name: str) -> Path:
    root = tmp / name
    shutil.copytree(ROOT / "spec", root / "spec")
    return root


def edit(root: Path, path: str, old: bytes, new: bytes, rehash: bool = True):
    """Replace one occurrence in a spec file; rehash it in VERSION.md so only
    the check under test can catch the change."""
    f = root / path
    before = hashlib.sha256(f.read_bytes()).hexdigest()
    data = f.read_bytes()
    assert old in data, f"probe text not in {path}"
    f.write_bytes(data.replace(old, new, 1))
    if rehash:
        after = hashlib.sha256(f.read_bytes()).hexdigest()
        v = root / "spec" / "VERSION.md"
        v.write_text(v.read_text(encoding="utf-8").replace(before, after), encoding="utf-8")


def outcome(root: Path) -> str:
    try:
        c.spec_identity(root=root)
        return "green"
    except c.Fail as e:
        return f"red: {e}"


def main() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        cases = []

        cases.append(("issued bundle unmodified", "green", scratch(tmp, "clean")))

        r = scratch(tmp, "row-byte")
        edit(r, ACC, b"\xe2\x89\xa4 200 KiB summed", b"\xe2\x89\xa4 210 KiB summed")
        cases.append(("one byte changed inside the WP-13 row", "red", r))

        r = scratch(tmp, "row-missing")
        edit(r, ACC, c.WP13_ROW_PREFIX, b"| **WP-13a** ")
        cases.append(("WP-13 row removed", "red", r))

        r = scratch(tmp, "row-dup")
        row = [l for l in (r / ACC).read_bytes().split(b"\n") if l.startswith(c.WP13_ROW_PREFIX)][0]
        edit(r, ACC, row, row + b"\n" + row)
        cases.append(("WP-13 row duplicated", "red", r))

        r = scratch(tmp, "manifest")
        edit(r, ACC, b"**WP-04, WP-05", b"**WP-04,  WP-05", rehash=False)
        cases.append(("spec file differs from spec/VERSION.md manifest", "red", r))

        r = scratch(tmp, "outside-row")
        edit(r, ACC, b"**WP-04, WP-05", b"**WP-04,  WP-05")
        cases.append(("edit outside the WP-13 row, manifest updated", "green", r))

        for name, want, root in cases:
            got = outcome(root)
            if got.split(":")[0] == want:
                print(f"  ok     {name} — goes {want} ({got})")
            else:
                print(f"  FAIL   {name} — wanted {want}, got {got}")
                ok = False
    print("WP-13 carry-over negative control:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
