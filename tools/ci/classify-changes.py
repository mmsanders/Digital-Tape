#!/usr/bin/env python3
"""Classify a pull request's changed paths as docs-only or full (#347).

A docs-only PR lets ci.yml skip the engine suite; anything else runs all of it.
Docs-only means EVERY changed path is one of:

  docs/**            except docs/verification/**
  site/**
  *.md               at the repository root only

Everything else is full, including docs/verification/**, spec/**, tests/**,
tools/**, engine/**, firmware/**, hardware/** and .github/**. An empty or
unreadable path list is full: the classifier fails toward running the suite.

Usage: git diff -z --no-renames --name-only A B | classify-changes.py
Reads NUL-separated paths on stdin, prints "docs-only" or "full", and, when
GITHUB_OUTPUT is set, appends docs_only=true|false to it.
"""
from __future__ import annotations

import os
import sys

DOCS_ONLY = "docs-only"
FULL = "full"


def docs_path(path: str) -> bool:
    if not path or path.startswith("/") or "\\" in path:
        return False
    parts = path.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return False
    if len(parts) == 1:
        return path.endswith(".md")
    if parts[0] == "docs":
        return parts[1] != "verification"
    return parts[0] == "site"


def classify(paths) -> str:
    paths = list(paths)
    if paths and all(docs_path(p) for p in paths):
        return DOCS_ONLY
    return FULL


def main() -> int:
    data = sys.stdin.buffer.read().decode("utf-8")
    paths = [p for p in data.split("\0") if p]
    verdict = classify(paths)
    print(f"{verdict}: {len(paths)} changed path(s)")
    for p in paths:
        print(f"  {'docs' if docs_path(p) else 'FULL'}  {p}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"docs_only={'true' if verdict == DOCS_ONLY else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
