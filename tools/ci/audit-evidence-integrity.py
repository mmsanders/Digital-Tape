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
  4. canonical spec/*.md match spec/VERSION.md, a declared revision; every
     embedded spec copy sits in a declared root and matches that root's revision
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


# --- 4. spec bytes: canonical bundle, and every embedded copy per root -----
# The bundle is versioned. Historical packages and retained evidence carry the
# spec bytes they were authenticated against, and those bytes are never
# rewritten (CLAUDE.md §3.1, §4). So an embedded copy is checked against the
# revision its own root DECLARES in tests/IMPORTS.json -- never inferred from a
# directory name, and never "either revision is fine everywhere".
SPEC_FILES = ("tapefs-v1.md", "engine-api.md", "acceptance.md")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
VERSION_ROW = re.compile(
    r"`spec/([a-z0-9.-]+\.md)`\s*\|\s*([A-Za-z0-9.-]+)\s*\|\s*`([0-9a-f]{64})`")


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _abs(path):
    p = pathlib.Path(path)
    return (p if p.is_absolute() else ROOT / p).resolve()


def _rel(path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _declared_revisions(sb):
    revs = sb.get("revisions")
    if not isinstance(revs, dict) or not revs:
        fail("spec-bundle", "tests/IMPORTS.json declares no spec bundle revisions")
        return None, {}
    complete = {}
    for name, triple in revs.items():
        if (not isinstance(triple, dict) or set(triple) != set(SPEC_FILES)
                or not all(isinstance(v, str) and HEX64.match(v) for v in triple.values())):
            fail("spec-bundle", f"revision {name} is not a complete triple of "
                                f"{', '.join(SPEC_FILES)} SHA-256 values")
            continue
        complete[name] = triple
    return revs, complete


def _check_canonical(sb, complete):
    vp = _abs(sb["manifest"])
    rows = VERSION_ROW.findall(vp.read_text(encoding="utf-8"))
    files = {f for f, _, _ in rows}
    if len(rows) != 3 or files != set(SPEC_FILES):
        fail("spec-bundle", f"could not parse exactly one row per spec file from {sb['manifest']}")
        return
    current = {r for _, r, _ in rows}
    if len(current) != 1:
        fail("spec-bundle", f"{sb['manifest']} mixes revisions {sorted(current)}")
        return
    rev = current.pop()
    want = {f: h for f, _, h in rows}
    if rev not in complete:
        fail("spec-bundle", f"{sb['manifest']} bundle {rev} is not a declared "
                            f"complete revision in tests/IMPORTS.json")
        return
    for f in SPEC_FILES:
        if want[f] != complete[rev][f]:
            fail("spec-bundle", f"{sb['manifest']} records {f} {want[f][:16]}…, but "
                                f"declared {rev} is {complete[rev][f][:16]}…")
    for f in SPEC_FILES:
        got = _sha256(ROOT / "spec" / f)
        if got != want[f]:
            fail("spec-bundle", f"spec/{f} is {got[:16]}…, {sb['manifest']} says {want[f][:16]}…")
    if not any(c == "spec-bundle" for c, _ in FAIL):
        ok("spec-bundle", f"spec/*.md match {sb['manifest']} ({rev})")


def check_spec_copies(m):
    sb = m["spec_bundle"]
    revs, complete = _declared_revisions(sb)
    if revs is None:
        return
    _check_canonical(sb, complete)

    roots = sb.get("roots")
    if not isinstance(roots, list) or not roots:
        fail("spec-copies", "tests/IMPORTS.json declares no spec copy roots")
        return
    declared = {}
    for r in roots:
        path, rev = r.get("path"), r.get("revision")
        if not path or not rev:
            fail("spec-copies", f"malformed root declaration {r}")
            continue
        key = _abs(path)
        if key in declared:
            fail("spec-copies", f"{path} is declared more than once")
            continue
        if rev not in revs:
            fail("spec-copies", f"{path} declares unknown bundle revision {rev}")
            continue
        declared[key] = (path, rev)

    found = {}
    for top in ("docs", "tests"):
        for f in (ROOT / top).rglob("*.md"):
            if f.name in SPEC_FILES:
                found.setdefault(f.parent.resolve(), set()).add(f.name)
    for parent in sorted(found):
        if parent not in declared:
            fail("spec-copies", f"{_rel(parent)} holds {', '.join(sorted(found[parent]))} "
                                f"but no bundle revision is declared for it")

    by_rev = {}
    for key, (path, rev) in sorted(declared.items()):
        if not key.is_dir():
            fail("spec-copies", f"declared root {path} does not exist")
            continue
        triple = complete.get(rev)
        if triple is None:
            fail("spec-copies", f"{path} declares {rev}, whose hash triple is incomplete")
            continue
        missing = [n for n in SPEC_FILES if not (key / n).is_file()]
        if missing:
            fail("spec-copies", f"{path} is an incomplete triple: missing {', '.join(missing)}")
        for n in SPEC_FILES:
            f = key / n
            if not f.is_file():
                continue
            got = _sha256(f)
            if got == triple[n]:
                continue
            other = [o for o, t in complete.items() if o != rev and t[n] == got]
            if other:
                fail("spec-copies", f"{path}/{n} is the {other[0]} copy, but the root "
                                    f"is declared {rev}")
            else:
                fail("spec-copies", f"{path}/{n} is {got[:16]}…, declared {rev} is "
                                    f"{triple[n][:16]}… (hash drift)")
        by_rev[rev] = by_rev.get(rev, 0) + 1
    if not found:
        fail("spec-copies", "found no spec copies to check — the check is not working")
    elif not any(c == "spec-copies" for c, _ in FAIL):
        summary = ", ".join(f"{n} {r}" for r, n in sorted(by_rev.items()))
        ok("spec-copies", f"{sum(len(v) for v in found.values())} copies in "
                          f"{len(declared)} declared roots ({summary}) all match "
                          f"their declared revision")


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
