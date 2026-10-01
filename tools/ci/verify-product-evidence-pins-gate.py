#!/usr/bin/env python3
"""Negative controls for the Product evidence pin audit (V-R54-01, #337).

CLAUDE.md §1: a gate that never goes red has not established what it detects.
Each probe copies tests/IMPORTS.json and every retained Product bundle into a
fresh temporary root, makes one change there, and requires
audit-product-evidence-pins.py --root <copy> to go red for that reason. It
mutates no real file and no git state.

  baseline        the unmodified copy is green
  reseal          one observation byte changed, gzip and SHA256SUMS regenerated
  unpinned        a new retained bundle directory with no pin
  deleted         a pinned bundle removed
"""
from __future__ import annotations

import gzip
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "tools/ci/audit-product-evidence-pins.py"
PATTERN = "tests/*_adapter/evidence/p1-r*-product"

passed = failed = 0


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fresh_copy(tmp: Path) -> Path:
    root = tmp / "repo"
    (root / "tests").mkdir(parents=True)
    shutil.copy2(ROOT / "tests/IMPORTS.json", root / "tests/IMPORTS.json")
    for d in ROOT.glob(PATTERN):
        rel = d.relative_to(ROOT)
        shutil.copytree(d, root / rel)
    return root


def run(root: Path) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-B", str(AUDIT), "--root", str(root)], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def expect(name: str, want_red: bool, root: Path, contains: str | None = None) -> None:
    global passed, failed
    rc, out = run(root)
    red = rc != 0
    ok = red == want_red and (contains is None or contains in out)
    if ok:
        print(f"  ok     {name} — goes {'red' if want_red else 'green'} on demand")
        passed += 1
    else:
        print(f"  BROKEN {name} — exit {rc}, expected {'red' if want_red else 'green'}"
              + (f" naming {contains!r}" if contains else ""))
        print("\n".join("           " + l for l in out.splitlines() if "FAIL" in l)[:2000])
        failed += 1


def reseal(root: Path) -> str:
    """Change one observation byte in a gzip-retained bundle, then regenerate the
    gzip and SHA256SUMS so every in-bundle checksum is self-consistent again."""
    for d in sorted(root.glob(PATTERN)):
        gz = d / "observations.jsonl.gz"
        sums = d / "SHA256SUMS"
        if gz.is_file() and sums.is_file():
            data = bytearray(gzip.decompress(gz.read_bytes()))
            i = next(k for k in range(len(data)) if chr(data[k]).isdigit())
            data[i] = ord("1") if data[i] != ord("1") else ord("2")
            new_gz = gzip.compress(bytes(data), compresslevel=9, mtime=0)
            gz.write_bytes(new_gz)
            lines = []
            for line in sums.read_text().splitlines():
                digest, name = line.split(None, 1)
                key = name.lstrip("*")
                if key == "observations.jsonl":
                    digest = sha(bytes(data))
                elif key == "observations.jsonl.gz":
                    digest = sha(new_gz)
                lines.append(f"{digest}  {name}")
            sums.write_text("\n".join(lines) + "\n")
            return d.relative_to(root).as_posix()
    raise SystemExit("no gzip-retained bundle to reseal")


def main() -> int:
    print("== product evidence pin gate can go red ==")
    with tempfile.TemporaryDirectory(prefix="pins-") as t:
        expect("baseline (unmodified copy)", False, fresh_copy(Path(t) / "a"))

        root = fresh_copy(Path(t) / "b")
        target = reseal(root)
        print(f"         resealed {target}")
        expect("rewrite and reseal one observation byte", True, root, contains="differs from its pin")

        root = fresh_copy(Path(t) / "c")
        new = root / "tests/unpinned_adapter/evidence/p1-r99-product"
        new.mkdir(parents=True)
        (new / "observations.jsonl").write_text('{"case":"x"}\n')
        expect("new unpinned retained bundle", True, root, contains="with no pin")

        root = fresh_copy(Path(t) / "d")
        victim = sorted(root.glob(PATTERN))[0]
        shutil.rmtree(victim)
        expect("deleted pinned bundle", True, root, contains="is missing")
    print(f"  {passed} passed, {failed} broken")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
