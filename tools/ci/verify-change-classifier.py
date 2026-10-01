#!/usr/bin/env python3
"""Negative controls for the docs-only change classifier (#347).

ci.yml skips the engine suite when tools/ci/classify-changes.py says a pull
request is docs-only, so a classifier that wrongly says docs-only silently
removes coverage. This script shows:

1. the real classifier returns FULL for every code-bearing path class and for
   mixed docs+code diffs, and docs-only only for the allowed paths;
2. the same table goes red against deliberately broken classifiers, so a
   classifier that never says "full" (or that admits one forbidden class)
   cannot pass it;
3. the CLI, fed NUL-separated paths as ci.yml feeds it, writes the GitHub
   output the workflow reads.

Exit status 1 if any expectation fails or any broken classifier survives.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/ci/classify-changes.py"

spec = importlib.util.spec_from_file_location("classify_changes", SCRIPT)
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
D, F = C.DOCS_ONLY, C.FULL

# (paths, expected verdict, label)
CASES = [
    (["docs/STATUS.md"], D, "docs/ file"),
    (["docs/archive/old.md", "docs/ROLES/README.md"], D, "nested docs/"),
    (["site/index.html"], D, "site/"),
    (["README.md"], D, "root *.md"),
    (["CLAUDE.md", "AGENTS.md", "docs/DECISIONS.md", "site/a.css"], D, "all three allowed classes"),
    ([], F, "empty diff"),
    (["engine/src/tape.c"], F, "engine/"),
    (["engine/README.md"], F, "*.md under engine/"),
    (["tests/IMPORTS.json"], F, "tests/"),
    (["tests/wp10_backlog_r54/README.md"], F, "*.md under tests/"),
    (["spec/tapefs-v1.md"], F, "spec/"),
    (["docs/verification/runs/x/manifest.json"], F, "docs/verification/"),
    (["docs/verification/README.md"], F, "*.md under docs/verification/"),
    (["docs/verification"], F, "docs/verification as a file"),
    ([".github/workflows/ci.yml"], F, ".github/"),
    ([".github/CODEOWNERS"], F, ".github/CODEOWNERS"),
    (["tools/ci/classify-changes.py"], F, "tools/"),
    (["firmware/main.c"], F, "firmware/"),
    (["hardware/board/notes.md"], F, "hardware/"),
    (["Makefile"], F, "root non-markdown file"),
    (["README.md.txt"], F, "root file that only contains .md"),
    (["docs/STATUS.md", "engine/src/tape.c"], F, "mixed docs + engine"),
    (["docs/STATUS.md", "tests/IMPORTS.json"], F, "mixed docs + tests"),
    (["README.md", "spec/VERSION.md"], F, "mixed root md + spec"),
    (["site/index.html", ".github/workflows/ci.yml"], F, "mixed site + .github"),
    (["docs/STATUS.md", "docs/verification/x.md"], F, "mixed docs + docs/verification"),
    (["docs/../engine/src/tape.c"], F, "dot-dot escape"),
    (["./docs/STATUS.md"], F, "non-canonical ./ path"),
    (["docs"], F, "bare docs as a file"),
]


def table(classify):
    """Failures of `classify` against CASES."""
    return [(label, want, classify(paths)) for paths, want, label in CASES if classify(paths) != want]


# Broken classifiers the table must reject.
def never_full(paths):
    return D


def any_instead_of_all(paths):
    return D if any(C.docs_path(p) for p in paths) else F


def empty_is_docs(paths):
    return D if all(C.docs_path(p) for p in paths) else F


def admits_docs_verification(paths):
    ok = lambda p: C.docs_path(p) or p.startswith("docs/verification/")  # noqa: E731
    return D if paths and all(ok(p) for p in paths) else F


def admits_any_markdown(paths):
    ok = lambda p: C.docs_path(p) or p.endswith(".md")  # noqa: E731
    return D if paths and all(ok(p) for p in paths) else F


def admits_github(paths):
    ok = lambda p: C.docs_path(p) or p.startswith(".github/")  # noqa: E731
    return D if paths and all(ok(p) for p in paths) else F


def prefix_without_slash(paths):
    ok = lambda p: (p.startswith("docs") and not p.startswith("docs/verification")) \
        or p.startswith("site") or ("/" not in p and p.endswith(".md"))  # noqa: E731
    return D if paths and all(ok(p) for p in paths) else F


MUTANTS = [never_full, any_instead_of_all, empty_is_docs, admits_docs_verification,
           admits_any_markdown, admits_github, prefix_without_slash]


def cli(paths):
    with tempfile.TemporaryDirectory() as t:
        out = pathlib.Path(t) / "out"
        r = subprocess.run([sys.executable, "-B", str(SCRIPT)], input="\0".join(paths).encode(),
                           capture_output=True, env={**os.environ, "GITHUB_OUTPUT": str(out)})
        return r.returncode, r.stdout.decode().splitlines()[0], out.read_text()


def main() -> int:
    bad = 0
    real = table(C.classify)
    for paths, want, label in CASES:
        got = C.classify(paths)
        print(f"{'ok  ' if got == want else 'FAIL'}  {want:<9} {label}: {paths}")
    if real:
        bad += 1
    for m in MUTANTS:
        caught = table(m)
        print(("killed   " if caught else "SURVIVED ") + f"{m.__name__}: {len(caught)} case(s) differ"
              + (f", e.g. {caught[0][0]} -> {caught[0][2]}" if caught else ""))
        if not caught:
            bad += 1
    for paths, want_out in ((["docs/STATUS.md", "README.md"], "docs_only=true\n"),
                            (["docs/STATUS.md", "engine/src/tape.c"], "docs_only=false\n"),
                            ([], "docs_only=false\n")):
        rc, line, out = cli(paths)
        good = rc == 0 and out == want_out
        print(f"{'ok  ' if good else 'FAIL'}  cli {paths} -> {line!r}, GITHUB_OUTPUT {out.strip()!r}")
        if not good:
            bad += 1
    full = sum(w == F for _, w, _ in CASES)
    print(f"{len(CASES) - len(real)}/{len(CASES)} cases ({full} full, {len(CASES) - full} docs-only); "
          f"{sum(1 for m in MUTANTS if table(m))}/{len(MUTANTS)} broken classifiers killed")
    print("== change classifier: " + ("PASS" if not bad else "FAIL") + " ==")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
