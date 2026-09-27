#!/usr/bin/env python3
"""One source of truth for the R29-C evidence identities, checked against git.

Every summary this binding publishes names the issued product base and the
verifier import commit. Hard-coding those as bare strings is how PR #236's first
evidence package came to cite PR #227's identities (Verification PR #79): the
strings were never compared with the history they describe.

verify() runs before any case executes, in every runner and in the aggregator.
It refuses to continue unless:

  - neither identity is one of the known-stale PR #227 values;
  - the import commit exists and is an ancestor of HEAD;
  - the import commit's parent is the issued product base;
  - the import commit carries exactly the pinned verifier tree, and HEAD still
    carries the same tree (no later commit edited it).

A reversion to a stale identity therefore fails before evidence is written.
test_provenance.py proves that each branch of this check can go red.
"""
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]

ISSUED_BASE = "ac1f1bfb3efa636e3c22fff4febc7d08f7b6d026"
IMPORT_COMMIT = "375d55ff6bbf328e7ff434012258dd1a3c1fe98a"
VERIFIER_TREE = "7e98b40c6aceb0a5759bfb1499091a4c9f541927"
VERIFIER_PATH = "tests/respool_full_draft8"

# PR #227 identities that PR #236's first package emitted by mistake.
STALE = {
    "8276d8f22da34a53f9f52dae8d3bd1acb3c763d9": "PR #227 claimed product base",
    "895351d17de9332e0804140858049d3608eeecd4": "PR #227 claimed verifier import",
}


class ProvenanceError(RuntimeError):
    pass


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
    ).strip()


def _git_ok(*args: str) -> bool:
    return subprocess.run(
        ["git", *args], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0


def verify(base: str = ISSUED_BASE, import_commit: str = IMPORT_COMMIT,
           verifier_tree: str = VERIFIER_TREE, git=None, git_ok=None) -> dict:
    """Return the verified identities, or raise ProvenanceError."""
    git = git or _git
    git_ok = git_ok or _git_ok

    for label, value in (("product base", base), ("verifier import", import_commit)):
        if value in STALE:
            raise ProvenanceError(f"stale {label} {value}: {STALE[value]}")

    if not git_ok("cat-file", "-e", f"{import_commit}^{{commit}}"):
        raise ProvenanceError(f"verifier import {import_commit} is not in this history")
    if not git_ok("merge-base", "--is-ancestor", import_commit, "HEAD"):
        raise ProvenanceError(f"verifier import {import_commit} is not an ancestor of HEAD")

    parent = git("rev-parse", f"{import_commit}^")
    if parent != base:
        raise ProvenanceError(f"import parent {parent} != declared product base {base}")

    imported = git("rev-parse", f"{import_commit}:{VERIFIER_PATH}")
    if imported != verifier_tree:
        raise ProvenanceError(f"import carries {VERIFIER_PATH} {imported} != {verifier_tree}")
    current = git("rev-parse", f"HEAD:{VERIFIER_PATH}")
    if current != verifier_tree:
        raise ProvenanceError(f"HEAD carries {VERIFIER_PATH} {current} != {verifier_tree}")

    return {
        "product_base": base,
        "verifier_import_commit": import_commit,
        "verifier_tree": verifier_tree,
    }


def check_emitted(summary: dict) -> None:
    """Refuse to publish a summary whose identities are not the verified ones."""
    if summary.get("product_base") != ISSUED_BASE:
        raise ProvenanceError(f"summary product_base {summary.get('product_base')} != {ISSUED_BASE}")
    if summary.get("verifier_import_commit") != IMPORT_COMMIT:
        raise ProvenanceError(
            f"summary verifier_import_commit {summary.get('verifier_import_commit')} != {IMPORT_COMMIT}"
        )
    if summary.get("verifier_tree") != VERIFIER_TREE:
        raise ProvenanceError(f"summary verifier_tree {summary.get('verifier_tree')} != {VERIFIER_TREE}")


if __name__ == "__main__":
    ids = verify()
    print("PASS provenance " + " ".join(f"{k}={v}" for k, v in sorted(ids.items())))
