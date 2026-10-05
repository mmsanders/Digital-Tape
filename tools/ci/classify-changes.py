#!/usr/bin/env python3
"""Classify a change for ci.yml's three lanes (#347 docs-only; #385 R1 lanes).

Outputs, appended to GITHUB_OUTPUT when it is set:

  docs_only=true|false   every changed path is a docs path:
                           docs/**  except docs/verification/**
                           site/**
                           *.md     at the repository root only
                         Docs-only changes run the cheap lane only.
  qualify=true|false     the whole qualification lane must run.
  qualify_jobs=",a,b,"   qualification jobs selected because one of their own
                         test directories changed (comma-delimited for contains()).

Everything fails toward running more. An empty or unreadable path list, an
event other than pull_request/push, a PR labelled `qualification`, or any path
not positively known to be inert sets qualify=true. The lane rules live in
tools/ci/ci_lanes.py; tools/ci/verify-change-classifier.py is their negative
control.

Usage: git diff -z --no-renames --name-only A B | classify-changes.py
Environment: EVENT (github.event_name), LABELS (comma-separated PR labels).
Reads NUL-separated paths on stdin and prints its verdict with reasons.
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ci_lanes as L  # noqa: E402

DOCS_ONLY = "docs-only"
FULL = "full"
docs_path = L.docs_path


def classify(paths) -> str:
    """The #347 docs-only verdict, unchanged."""
    paths = list(paths)
    if paths and all(docs_path(p) for p in paths):
        return DOCS_ONLY
    return FULL


def main() -> int:
    data = sys.stdin.buffer.read().decode("utf-8")
    paths = [p for p in data.split("\0") if p]
    event = os.environ.get("EVENT", "pull_request")
    labels = os.environ.get("LABELS", "").split(",")
    deps = L.qualification_deps(L.WORKFLOW.read_text())
    docs_only, qualify, jobs, reasons = L.classify_paths(paths, event, labels, deps)
    if docs_only:
        qualify, jobs = False, set()
    padded = L.format_qualify_jobs(jobs)

    print(f"{'docs-only' if docs_only else 'full'}: {len(paths)} changed path(s), event {event}")
    for p in paths:
        print(f"  {'docs' if docs_path(p) else 'CODE'}  {p}")
    print(f"qualification: {'ALL' if qualify else ('only' + padded if jobs else 'none')}")
    for r in reasons:
        print(f"  {r}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"docs_only={'true' if docs_only else 'false'}\n")
            f.write(f"qualify={'true' if qualify else 'false'}\n")
            f.write(f"qualify_jobs={padded}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
