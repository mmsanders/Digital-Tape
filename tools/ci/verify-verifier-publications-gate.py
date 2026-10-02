#!/usr/bin/env python3
"""Negative control for audit-verifier-publications.py (CLAUDE.md §1).

Builds a throwaway verifier repository with a merged publication, an unmerged
PR-branch publication, and a legacy carrier, then shows the gate goes green on
the lawful cases and red, for the named reason, on each failure mode. It touches
no real file, no real manifest and no network.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
GATE = ROOT / "tools/ci/audit-verifier-publications.py"
SRC = "mmsanders/digital-tape-verification"

passed = failed = 0


def git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="control", GIT_AUTHOR_EMAIL="c@x",
               GIT_COMMITTER_NAME="control", GIT_COMMITTER_EMAIL="c@x")
    r = subprocess.run(["git", "-C", str(repo), *args], env=env,
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def commit_file(repo, rel, text, msg):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


def pkg(path, tree, commit):
    return {"path": path, "tree": tree, "source_repo": SRC,
            "source_commit": commit}


def expect(want, name, tmp, repo, packages, legacy=None, saying=None):
    global passed, failed
    man = tmp / "IMPORTS.json"
    man.write_text(json.dumps({"packages": packages}), encoding="utf-8")
    leg = tmp / "legacy.json"
    leg.write_text(json.dumps(legacy or {}), encoding="utf-8")
    env = dict(os.environ, EVIDENCE_MANIFEST=str(man), VERIFIER_REPO=str(repo),
               VERIFIER_MAIN="main", VERIFIER_LEGACY=str(leg))
    r = subprocess.run([sys.executable, str(GATE)], env=env,
                       capture_output=True, text=True)
    out = r.stdout + r.stderr
    red = r.returncode == 1
    good = red if want == "red" else r.returncode == 0
    if good and want == "red" and saying and f"[{saying}]" not in out:
        good = False
    if good:
        print(f"  ok     {name} — goes {want} on demand")
        passed += 1
    else:
        print(f"  BROKEN {name} — expected {want}"
              f"{' naming [' + saying + ']' if saying else ''}, exit {r.returncode}")
        print("         " + out.replace("\n", "\n         "))
        failed += 1


def main():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        repo = tmp / "verification"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        merged = commit_file(repo, "tests/pkg_a/oracle.py", "a = 1\n", "publish a")
        tree_a = git(repo, "rev-parse", f"{merged}:tests/pkg_a")
        # A later correction on main changes the package; the cited commit's
        # tree is still what was imported, so the citation stays green.
        commit_file(repo, "tests/pkg_a/oracle.py", "a = 2\n", "later fix")
        # A publication that exists only on an open PR branch.
        git(repo, "checkout", "-q", "-b", "pr-branch")
        unmerged = commit_file(repo, "tests/pkg_b/oracle.py", "b = 1\n", "publish b")
        tree_b = git(repo, "rev-parse", f"{unmerged}:tests/pkg_b")
        git(repo, "checkout", "-q", "main")
        # A legacy carrier: same tree as a lost publication, landed on main.
        carrier = commit_file(repo, "tests/pkg_c/oracle.py", "c = 1\n", "carry c")
        tree_c = git(repo, "rev-parse", f"{carrier}:tests/pkg_c")
        lost = "0123456789abcdef0123456789abcdef01234567"
        legacy = {"tests/pkg_c": {"cited": lost, "carrier": carrier}}

        print("verifier publication gate negative controls")
        expect("green", "merged publication with its declared tree", tmp, repo,
               [pkg("tests/pkg_a", tree_a, merged)])
        expect("green", "short source_commit resolves", tmp, repo,
               [pkg("tests/pkg_a", tree_a, merged[:10])])
        expect("red", "publication only on an open PR branch", tmp, repo,
               [pkg("tests/pkg_b", tree_b, unmerged)], saying="unmerged")
        expect("red", "declared tree differs from the cited commit", tmp, repo,
               [pkg("tests/pkg_a", tree_b, merged)], saying="tree")
        expect("red", "cited commit does not exist", tmp, repo,
               [pkg("tests/pkg_a", tree_a, lost)], saying="missing")
        expect("green", "legacy carrier on main with the declared tree", tmp,
               repo, [pkg("tests/pkg_c", tree_c, lost)], legacy=legacy)
        expect("red", "legacy carrier with the wrong tree", tmp, repo,
               [pkg("tests/pkg_c", tree_a, lost)], legacy=legacy,
               saying="legacy")
        expect("red", "legacy exception cannot cover an unlisted path", tmp,
               repo, [pkg("tests/pkg_a", tree_a, lost)], legacy=legacy,
               saying="missing")
        # Merging the PR branch is exactly what turns the red case green.
        git(repo, "merge", "-q", "--no-ff", "--no-edit", "pr-branch")
        expect("green", "same publication after its PR merges", tmp, repo,
               [pkg("tests/pkg_b", tree_b, unmerged)])
        # Squash-merging would not: the cited SHA stays off main.
        git(repo, "reset", "-q", "--hard", "HEAD~1")
        git(repo, "merge", "-q", "--squash", "pr-branch")
        git(repo, "commit", "-q", "-m", "squash b")
        expect("red", "squash merge leaves the cited SHA off main", tmp, repo,
               [pkg("tests/pkg_b", tree_b, unmerged)], saying="unmerged")

    print(f"\n{passed} ok, {failed} broken")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
