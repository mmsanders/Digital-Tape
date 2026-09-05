#!/usr/bin/env python3
"""spec/hw version manifest — the CHANGES obligation, made mechanical.

`board-rev-a.md` is what firmware writes against, and its value rests on the
document changing first with an explicit notification. This gate fails if a
file's content moved while its revision did not.

    make -C hardware spec-check   verify
    make -C hardware spec-bless   record intended revision bumps
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

HW = Path(__file__).resolve().parents[1] / "spec" / "hw"
MANIFEST = HW / "VERSION.md"
TRACKED = ("board-rev-a.md", "thermal-budget.md", "cartridge-shell.md")
ROW = re.compile(r"^\| `(?P<f>[\w.-]+)` \| (?P<rev>[\d.]+) \| `(?P<sha>[0-9a-f]{64}|AUTO)` \|$",
                 re.M)


def content_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declared_revision(path: Path) -> str | None:
    m = re.search(r"\*\*Revision:\*\*\s*([\d.]+)", path.read_text())
    return m.group(1) if m else None


def rows() -> dict[str, tuple[str, str]]:
    return {m["f"]: (m["rev"], m["sha"]) for m in ROW.finditer(MANIFEST.read_text())}


def main() -> int:
    bless = "--bless" in sys.argv
    recorded = rows()
    problems, updates = [], {}

    for name in TRACKED:
        p = HW / name
        if not p.exists():
            problems.append(f"{name}: tracked by the manifest but missing")
            continue
        sha, rev = content_sha(p), declared_revision(p)
        if rev is None:
            problems.append(f"{name}: no '**Revision:**' line to check against")
            continue
        if name not in recorded:
            problems.append(f"{name}: not in the manifest")
            continue
        rec_rev, rec_sha = recorded[name]
        if bless:
            updates[name] = (rev, sha)
            continue
        if rec_sha == "AUTO":
            updates[name] = (rev, sha)
            problems.append(
                f"{name}: manifest row is AUTO -- never blessed, so nothing is being "
                f"checked. Run `make -C hardware spec-bless`.")
            continue
        if sha != rec_sha and rev == rec_rev:
            problems.append(
                f"{name}: content changed but **Revision:** is still {rev}. "
                f"Bump it, add a CHANGES entry, then `make -C hardware spec-bless`.")
        elif sha != rec_sha:
            updates[name] = (rev, sha)
            if not bless:
                problems.append(
                    f"{name}: revision moved {rec_rev} -> {rev} but the manifest still "
                    f"holds the old hash. Run `make -C hardware spec-bless`.")

    if bless:
        text = MANIFEST.read_text()
        for name, (rev, sha) in updates.items():
            # One unambiguous rewrite per row. An alternation inside the pattern
            # was matching across the row boundary and corrupting the table --
            # match the row by its filename only, and replace it whole.
            text = re.sub(rf"^\| `{re.escape(name)}` \|[^\n]*$",
                          f"| `{name}` | {rev} | `{sha}` |", text, flags=re.M)
        MANIFEST.write_text(text)
        if bless:
            for name, (rev, sha) in updates.items():
                print(f"blessed {name} at revision {rev} ({sha[:12]}…)")
            return 0

    if problems:
        for p in problems:
            print(f"FAIL spec/hw: {p}", file=sys.stderr)
        return 1
    print(f"OK  spec/hw manifest: {len(TRACKED)} files, content and revision agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
