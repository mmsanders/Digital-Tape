#!/usr/bin/env python3
"""Evidence integrity gate — the mechanical half of PM authentication.

STATUS recorded twenty "PM authenticated / PM reproduced the full suite" events.
Every tranche was executed three times: lead, PM, Verification. The checks below
are exactly the mechanical ones PM did by hand. They are not judgment, and they
do not accept anything: a green run here is not a disposition, not a package
acceptance, and not independent review. PM still rules on substance.

Checks, all declared in tests/IMPORTS.json:

  1. imported verifier subtree hash equals the declared publication tree
  2. package self-tests green for every tests/*_draft8/ package touched
  3. offline replay of each retained evidence bundle matches its declared outcome
  4. every copy of a frozen spec file hashes to spec/VERSION.md
  5. manifest adapter kind/ID equals observation adapter kind/ID
  6. Structural Rule 1 ordering: on a branch carrying both an import and an
     implementation, every verifier-tree change precedes every engine change

Usage: audit-evidence-integrity.py [BASE_REF]
Exit 0 green, 1 red, 2 harness error.
"""
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
FAIL = []
NOTE = []


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)


def fail(check, msg):
    FAIL.append((check, msg))
    print(f"  FAIL  [{check}] {msg}")


def ok(check, msg):
    print(f"  ok    [{check}] {msg}")


def load_manifest():
    # EVIDENCE_MANIFEST lets the negative control point at a doctored manifest in
    # a temp dir, so it can prove each check goes red without mutating a single
    # real file. CI never sets it.
    override = os.environ.get("EVIDENCE_MANIFEST")
    p = pathlib.Path(override) if override else ROOT / "tests/IMPORTS.json"
    if not p.exists():
        print(f"harness error: manifest {p} is missing", file=sys.stderr)
        sys.exit(2)
    return json.loads(p.read_text(encoding="utf-8"))


def touched_paths(base):
    """Paths changed against base, or None when no usable base ref."""
    if not base:
        return None
    if run(["git", "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"]).returncode:
        return None
    r = run(["git", "diff", "--name-only", f"{base}...HEAD"])
    if r.returncode:
        return None
    return set(r.stdout.split())


# --- 1. subtree identity -----------------------------------------------------
def check_subtrees(m):
    for pkg in m["packages"]:
        path, want = pkg["path"], pkg["tree"]
        r = run(["git", "rev-parse", f"HEAD:{path}"])
        if r.returncode:
            fail("subtree", f"{path} is not in HEAD")
            continue
        got = r.stdout.strip()
        if got != want:
            fail("subtree", f"{path} tree is {got}, declared {want} "
                            f"(attested in {pkg['attested_in']})")
        else:
            ok("subtree", f"{path} == {want[:12]}  [{pkg['attested_in']}]")


# --- 2. package self-tests ---------------------------------------------------
def check_selftests(m, touched):
    for pkg in m["packages"]:
        path = pkg["path"]
        if touched is not None and not any(t.startswith(path + "/") or t == path
                                           for t in touched):
            NOTE.append(f"{path} untouched by this PR; self-test skipped")
            print(f"  skip  [selftest] {path} untouched by this PR")
            continue
        r = run(pkg["selftest"])
        if r.returncode:
            tail = (r.stdout + r.stderr).strip().splitlines()[-4:]
            fail("selftest", f"{path}: {' '.join(pkg['selftest'])} exited "
                            f"{r.returncode}\n        " + "\n        ".join(tail))
        else:
            ok("selftest", f"{path} green")


# --- 3. offline replay -------------------------------------------------------
def check_replay(m):
    for b in m["evidence_bundles"]:
        path, expect = b["path"], b["expect"]
        if not (ROOT / path).is_dir():
            fail("replay", f"{path} is missing")
            continue
        obs = ROOT / path / "output/observation.json"
        if not obs.exists():
            fail("replay",
                 f"{path}/output/observation.json is absent. Raw evidence over "
                 f"1 MiB lives in a release asset, not the tree: run "
                 f"tools/fetch-evidence.sh, which verifies it against the "
                 f"committed .sha256 before installing it.")
            continue
        r = run(["python3", b["replay"], path], timeout=1800)
        passed = r.returncode == 0
        if expect == "pass" and not passed:
            fail("replay", f"{path} must replay green but exited {r.returncode}: "
                           f"{(r.stdout + r.stderr).strip().splitlines()[-1:]}")
        elif expect == "refuse" and passed:
            fail("replay", f"{path} replayed GREEN but is declared refused. "
                           f"{b['why']} A pass here means the control stopped working.")
        else:
            ok("replay", f"{path} {'PASS' if passed else 'refused'} as declared")


# --- 4. spec bytes in every evidence and package tree ------------------------
def check_spec_copies(m):
    vp = pathlib.Path(m["spec_bundle"]["manifest"])
    ver = (vp if vp.is_absolute() else ROOT / vp).read_text(encoding="utf-8")
    want = dict(re.findall(r"`spec/([a-z0-9.-]+\.md)`\s*\|[^|]*\|\s*`([0-9a-f]{64})`", ver))
    if len(want) != 3:
        fail("spec-copies", f"could not parse 3 hashes from {m['spec_bundle']['manifest']}")
        return
    checked = 0
    for top in ("docs", "tests"):
        for f in (ROOT / top).rglob("*.md"):
            if f.name not in want:
                continue
            got = hashlib.sha256(f.read_bytes()).hexdigest()
            checked += 1
            if got != want[f.name]:
                fail("spec-copies", f"{f.relative_to(ROOT)} is {got[:16]}…, "
                                    f"bundle says {want[f.name][:16]}…")
    if checked == 0:
        fail("spec-copies", "found no spec copies to check — the check is not working")
    elif not any(c == "spec-copies" for c, _ in FAIL):
        ok("spec-copies", f"{checked} copies all match spec/VERSION.md")


# --- 5. adapter identity binding ---------------------------------------------
def check_adapter_identity(m):
    for b in m["evidence_bundles"]:
        bp = pathlib.Path(b["path"])
        base = bp if bp.is_absolute() else ROOT / bp
        mf, obs = base / "manifest.json", base / "output/observation.json"
        if not (mf.exists() and obs.exists()):
            fail("adapter-id", f"{b['path']} is missing manifest.json or observation.json")
            continue
        try:
            a = json.loads(mf.read_text())["adapter"]
            o = json.loads(obs.read_text())["adapter"]
        except (KeyError, json.JSONDecodeError) as e:
            fail("adapter-id", f"{b['path']}: {e}")
            continue
        if (a.get("kind"), a.get("id")) != (o.get("kind"), o.get("id")):
            fail("adapter-id", f"{b['path']} manifest {a.get('kind')}/{a.get('id')} "
                               f"!= observation {o.get('kind')}/{o.get('id')}")
        else:
            ok("adapter-id", f"{b['path']} {a.get('kind')}/{a.get('id')}")


# --- 6. Structural Rule 1, mechanised ------------------------------------------
# Verifier-owned packages use the top-level tests/*_draft8 convention. Keep this
# rule convention-based rather than enumerating today's imports: a newly published
# verifier package is protected on its first product-side import commit, before
# tests/IMPORTS.json is even used to authenticate its exact tree.
VERIFIER_PACKAGE_RE = re.compile(r"^tests/[^/]+_draft8(?:/|$)")
IMPL_PREFIXES = ("engine/", "firmware/")


def is_verifier_package_path(path):
    return bool(VERIFIER_PACKAGE_RE.match(path))


def check_structural_rule_1(base):
    """Tests land before implementation -- proven from history, not asserted.

    D-2 collapsed the import and the implementation onto one branch. What used
    to be guaranteed by two separate merges is now guaranteed here: on a branch
    carrying both, every commit touching a verifier package tree must come
    strictly before every commit touching engine/ or firmware/, and no single
    commit may do both.

    This is what preserves verifier blindness under the collapsed protocol. The
    implementer still cannot tune an assertion, because the imported tree is
    byte-identical to a publication (check 1) landed in an earlier commit than
    the code (this check).
    """
    if not base:
        print("  skip  [rule-1] no base ref; ordering not checked")
        return
    if run(["git", "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"]).returncode:
        print("  skip  [rule-1] base ref unavailable")
        return
    r = run(["git", "rev-list", "--reverse", f"{base}..HEAD"])
    commits = [c for c in r.stdout.split() if c]
    if not commits:
        print("  skip  [rule-1] no commits against base")
        return

    first_impl = None
    last_pkg = None
    for i, c in enumerate(commits):
        files = run(["git", "show", "--pretty=", "--name-only", c]).stdout.split("\n")
        pkg = any(is_verifier_package_path(f) for f in files if f)
        impl = any(f.startswith(IMPL_PREFIXES) for f in files if f)
        if pkg and impl:
            fail("rule-1", f"commit {c[:12]} changes a verifier package tree AND "
                           f"implementation in the same commit; the import must be "
                           f"its own commit, landing first")
            return
        if pkg and last_pkg is None or pkg:
            last_pkg = i
        if impl and first_impl is None:
            first_impl = i

    if last_pkg is None or first_impl is None:
        ok("rule-1", "branch carries an import or an implementation, not both")
        return
    if last_pkg > first_impl:
        fail("rule-1",
             f"commit {commits[last_pkg][:12]} changes a verifier package tree "
             f"after implementation landed at {commits[first_impl][:12]}. Tests "
             f"land before implementation (CLAUDE.md §3.1); a package change "
             f"made after the code is how an assertion gets tuned to fit it.")
    else:
        ok("rule-1", f"import at commit {last_pkg + 1} precedes implementation "
                     f"at commit {first_impl + 1} of {len(commits)}")


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else ""
    touched = touched_paths(base)
    print("== evidence integrity ==")
    if touched is None:
        print("  note  no usable base ref; running every package self-test")
    m = load_manifest()
    check_subtrees(m)
    check_selftests(m, touched)
    check_replay(m)
    check_spec_copies(m)
    check_adapter_identity(m)
    check_structural_rule_1(base)
    print(f"== evidence integrity: {'FAIL' if FAIL else 'PASS'} "
          f"({len(FAIL)} failed) ==")
    print("   A green run here is mechanical authentication only. It is not a")
    print("   disposition, not package acceptance, and not independent review.")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
