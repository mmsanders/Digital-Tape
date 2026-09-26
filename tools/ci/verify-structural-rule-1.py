#!/usr/bin/env python3
"""Negative control for the Structural Rule 1 ordering check.

D-2 collapsed the test import and the implementation onto one branch. The thing
that used to be guaranteed by two separate merges is now guaranteed by a CI
check, so that check has to be shown to fail when the ordering is wrong --
otherwise the collapse quietly removes the guarantee instead of relocating it
(CLAUDE.md §1).

It builds a THROWAWAY git repository in a temp directory and commits into that.
It never touches this repository's HEAD, index, refs or worktree: an earlier
negative control in this project used `git reset --hard` and destroyed an
unrelated commit, and nothing here may risk repeating it.
"""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
GATE = ROOT / "tools/ci/audit-evidence-integrity.py"

passed = failed = 0


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)


def commit(repo, path, text, message):
    f = repo / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=c@local", "-c", "user.name=control",
        "commit", "-q", "-m", message)


def build_repo(tmp):
    """A minimal repo where only the ordering check has anything to say."""
    repo = pathlib.Path(tmp) / "repo"
    (repo / "tools/ci").mkdir(parents=True)
    shutil.copy(GATE, repo / "tools/ci/audit-evidence-integrity.py")

    # Stand-ins for the three frozen files, so the spec-copies check has
    # something consistent to verify and only the ordering check can speak.
    (repo / "docs").mkdir(parents=True, exist_ok=True)
    (repo / "spec").mkdir(parents=True, exist_ok=True)
    # The same bytes serve as the canonical spec/ files and as one declared
    # embedded root, so the bundle-version checks (#248) are satisfied too.
    rows = []
    triple = {}
    for name in ("tapefs-v1.md", "engine-api.md", "acceptance.md"):
        text = f"# a stand-in for frozen {name}\n"
        (repo / "docs" / name).write_text(text, encoding="utf-8")
        (repo / "spec" / name).write_text(text, encoding="utf-8")
        digest = hashlib.sha256(text.encode()).hexdigest()
        triple[name] = digest
        rows.append(f"| `spec/{name}` | DRAFT-8 | `{digest}` |")
    (repo / "spec/VERSION.md").write_text(
        "| File | Revision | SHA-256 |\n|---|---|---|\n" + "\n".join(rows) + "\n",
        encoding="utf-8")

    (repo / "tests").mkdir(parents=True, exist_ok=True)
    (repo / "tests/IMPORTS.json").write_text(json.dumps({
        "packages": [], "evidence_bundles": [],
        "spec_bundle": {
            "manifest": "spec/VERSION.md",
            "revisions": {"DRAFT-8": triple},
            "roots": [{"path": "docs", "revision": "DRAFT-8"}],
        },
    }), encoding="utf-8")

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=c@local", "-c", "user.name=control",
        "commit", "-q", "-m", "base")
    return repo


def run_gate(repo, base):
    r = subprocess.run([sys.executable, str(repo / "tools/ci/audit-evidence-integrity.py"), base],
                       cwd=repo, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def expect(want, name, repo, base):
    global passed, failed
    rc, out = run_gate(repo, base)
    red = rc != 0
    good = (want == "red" and red) or (want == "green" and not red)
    if good and want == "red" and "[rule-1]" not in out:
        good, why = False, "went red but never named [rule-1]"
    else:
        why = f"expected {want}, gate exited {rc}"
    if good:
        print(f"  ok     {name} — goes {want} on demand")
        passed += 1
    else:
        print(f"  BROKEN {name} — {why}")
        for line in out.splitlines():
            if "FAIL" in line or "rule-1" in line:
                print(f"         {line}")
        failed += 1


def main():
    print("== Structural Rule 1 ordering check can go red for any *_draft8 package ==")
    with tempfile.TemporaryDirectory() as tmp:
        # correct order: the import lands, then the implementation
        repo = build_repo(tmp)
        base = git(repo, "rev-parse", "HEAD").stdout.strip()
        commit(repo, "tests/future_draft8/oracle.py", "# imported verbatim\n", "import")
        commit(repo, "engine/src/alloc.c", "/* implementation */\n", "implement")
        expect("green", "import commit precedes implementation", repo, base)

        # wrong order: the package tree changes after the code
        repo = build_repo(pathlib.Path(tmp) / "b")
        base = git(repo, "rev-parse", "HEAD").stdout.strip()
        commit(repo, "engine/src/alloc.c", "/* implementation */\n", "implement")
        commit(repo, "tests/future_draft8/oracle.py", "# tweaked after the fact\n", "adjust tests")
        expect("red", "package tree changed after implementation", repo, base)

        # both in one commit: no separable import
        repo = build_repo(pathlib.Path(tmp) / "c")
        base = git(repo, "rev-parse", "HEAD").stdout.strip()
        f1 = repo / "tests/future_draft8/oracle.py"
        f2 = repo / "engine/src/alloc.c"
        for f, t in ((f1, "# import\n"), (f2, "/* impl */\n")):
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(t, encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "-c", "user.email=c@local", "-c", "user.name=control",
            "commit", "-q", "-m", "import and implement together")
        expect("red", "import and implementation in one commit", repo, base)

    print(f"  {passed} passed, {failed} broken")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
