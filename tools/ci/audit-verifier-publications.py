#!/usr/bin/env python3
"""Verifier publication gate: every cited verifier commit is on verification main.

ADR-155 step 1 says Verification publishes to `digital-tape-verification/main`.
From 27 September to 2 October nothing was merged there: Product imported eleven
packages from open PR heads, and one more from a correction pushed after its PR
had merged. Each was byte-identical to its publication, but a commit that lives
only on a PR branch is not a publication of record. Deleting, rebasing or
squashing that branch would orphan the commit and leave the citation pointing at
nothing (ADR-157). This gate makes that state red instead of invisible.

For every tests/IMPORTS.json package whose source_repo is the verification repo:

  [missing]   source_commit resolves to a commit in the verification repo
  [unmerged]  that commit is an ancestor of verification main
  [tree]      the commit's subtree at the package path equals the declared tree
  [legacy]    a pre-ADR-157 carrier exception (below) still holds exactly

The verification repo is public, so no token is needed. This is the
cross-repository check that ADR-155's "stated limitation" said was missing.

A green run accepts nothing. It authenticates where the publication lives; it
does not dispose, accept or replace independent review (CLAUDE.md §3.4).

Environment (the negative control uses these; CI normally sets none):
  EVIDENCE_MANIFEST  manifest path        (default tests/IMPORTS.json)
  VERIFIER_REPO      local clone to read  (default: blobless clone of the public repo)
  VERIFIER_MAIN      ref naming main      (default origin/main, else main)
  VERIFIER_LEGACY    JSON file replacing LEGACY_CARRIERS

Exit 0 green, 1 red, 2 harness error.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE_REPO = "mmsanders/digital-tape-verification"
CLONE_URL = f"https://github.com/{SOURCE_REPO}.git"

# Two Phase-0 publications cite commits that never reached verification main and
# no longer exist anywhere. Their exact declared trees reached main later, carried
# by 62b18de (13 Sep). The exception is pinned to that carrier and tree, so it
# cannot cover anything new. Do not add entries: a new citation must be merged.
LEGACY_CARRIERS = {
    "tests/mount_draft8": {
        "cited": "4ee116fa040bb5ce040325e0076365abf8b0f8f9",
        "carrier": "62b18deb8b4fbe6e797b00d792ee9f46ac0a8059",
    },
    "tests/playback_draft8": {
        "cited": "7a22cbb4447c40c51b7c8b2282a685ed30a46ba6",
        "carrier": "62b18deb8b4fbe6e797b00d792ee9f46ac0a8059",
    },
}

FAIL = []


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)


def resolve(repo, rev):
    r = git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    return r.stdout.strip() if r.returncode == 0 else None


def on_main(repo, commit, main):
    return git(repo, "merge-base", "--is-ancestor", commit, main).returncode == 0


def tree_at(repo, commit, path):
    r = git(repo, "rev-parse", "--verify", "--quiet", f"{commit}:{path}")
    return r.stdout.strip() if r.returncode == 0 else None


def verifier_clone():
    given = os.environ.get("VERIFIER_REPO")
    if given:
        return pathlib.Path(given), None
    tmp = tempfile.TemporaryDirectory()
    dest = pathlib.Path(tmp.name) / "verification"
    r = subprocess.run(["git", "clone", "--quiet", "--filter=blob:none",
                        "--no-checkout", CLONE_URL, str(dest)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"harness: cannot clone {CLONE_URL}: {r.stderr.strip()}")
        sys.exit(2)
    return dest, tmp


def main_ref(repo):
    want = os.environ.get("VERIFIER_MAIN")
    for ref in ([want] if want else ["origin/main", "main"]):
        if resolve(repo, ref):
            return ref
    print("harness: verification main not found")
    sys.exit(2)


def check(repo, main, pkg, legacy):
    path, tree, cited = pkg["path"], pkg["tree"], pkg.get("source_commit", "")
    commit = resolve(repo, cited) if cited else None
    if commit and on_main(repo, commit, main):
        got = tree_at(repo, commit, path)
        if got != tree:
            FAIL.append(f"[tree] {path}: {cited} has {got or 'no such path'}, "
                        f"IMPORTS declares {tree}")
            return
        print(f"  ok  {path} {commit[:12]} on main, tree {tree[:12]}")
        return
    exc = legacy.get(path)
    if exc and cited and exc["cited"].startswith(cited) and not commit:
        carrier = resolve(repo, exc["carrier"])
        if (carrier and on_main(repo, carrier, main)
                and tree_at(repo, carrier, path) == tree):
            print(f"  ok  {path} legacy: cited {cited[:12]} absent; "
                  f"tree {tree[:12]} carried on main by {carrier[:12]}")
        else:
            FAIL.append(f"[legacy] {path}: carrier {exc['carrier'][:12]} is not "
                        f"on main with tree {tree}")
        return
    if not commit:
        FAIL.append(f"[missing] {path}: source_commit {cited or '(none)'} "
                    f"does not exist in {SOURCE_REPO}")
    else:
        FAIL.append(f"[unmerged] {path}: source_commit {commit} is not on "
                    f"verification main. Merge its PR (merge commit, never "
                    f"squash or rebase) before importing it")


def main():
    mpath = pathlib.Path(os.environ.get("EVIDENCE_MANIFEST",
                                        ROOT / "tests/IMPORTS.json"))
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    legacy = LEGACY_CARRIERS
    if os.environ.get("VERIFIER_LEGACY"):
        legacy = json.loads(pathlib.Path(os.environ["VERIFIER_LEGACY"])
                            .read_text(encoding="utf-8"))
    repo, _keep = verifier_clone()
    main = main_ref(repo)
    pkgs = [p for p in manifest.get("packages", [])
            if p.get("source_repo") == SOURCE_REPO]
    print(f"verification main {resolve(repo, main)} ({main}); "
          f"{len(pkgs)} cited packages")
    for p in pkgs:
        check(repo, main, p, legacy)
    if FAIL:
        print("\nRED: cited verifier publications not on verification main")
        for f in FAIL:
            print("  " + f)
        sys.exit(1)
    print(f"\nGREEN: all {len(pkgs)} cited publications are on verification main")


if __name__ == "__main__":
    main()
