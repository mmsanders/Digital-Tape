#!/usr/bin/env python3
"""Focused negative controls for the evidence-integrity gate.

CLAUDE.md §1 requires every gate to demonstrate that it can go red. The sibling
"evidence integrity" CI job already proves the complete real manifest goes
green. This script therefore uses the smallest manifest needed for each failure
mode instead of replaying the full real manifest before and after every probe.

It mutates no real file and no git state. Every probe writes a temporary
EVIDENCE_MANIFEST. The subtree probe doctors the declared hash rather than
committing a tampered tree; the comparison exercised is the same.
"""
import copy
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
GATE = ROOT / "tools/ci/audit-evidence-integrity.py"
REAL = json.loads((ROOT / "tests/IMPORTS.json").read_text(encoding="utf-8"))

passed = failed = 0


def run_gate(manifest_obj, tmp, base="HEAD"):
    p = pathlib.Path(tmp) / "IMPORTS.json"
    p.write_text(json.dumps(manifest_obj), encoding="utf-8")
    env = dict(os.environ, EVIDENCE_MANIFEST=str(p))
    cmd = [sys.executable, str(GATE)]
    if base:
        cmd.append(base)
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def expect(want, name, manifest_obj, tmp, saying=None, base="HEAD", contains=None):
    global passed, failed
    rc, out = run_gate(manifest_obj, tmp, base=base)
    red = rc != 0
    good = (want == "red" and red) or (want == "green" and not red)
    if good and saying and want == "red" and f"[{saying}]" not in out:
        good = False
        why = f"went red but never named [{saying}]"
    elif good and contains and want == "red" and contains not in out:
        # A probe that goes red for some other reason proves nothing about the
        # classification it names.
        good = False
        why = f"went red but not for: {contains!r}"
    else:
        why = f"expected {want}, gate exited {rc}"
    if good:
        print(f"  ok     {name} — goes {want} on demand")
        passed += 1
    else:
        print(f"  BROKEN {name} — {why}")
        for line in out.splitlines():
            if "FAIL" in line or "error" in line:
                print(f"         {line}")
        failed += 1


def minimal(*, packages=None, evidence_bundles=None, spec_bundle=None):
    return {
        "packages": [] if packages is None else packages,
        "evidence_bundles": [] if evidence_bundles is None else evidence_bundles,
        "spec_bundle": copy.deepcopy(REAL["spec_bundle"] if spec_bundle is None else spec_bundle),
    }


def check_preconditions():
    """Only the replay probe needs retained real evidence."""
    if not REAL.get("evidence_bundles"):
        print("PRECONDITION UNMET: no retained evidence bundle is declared")
        return False
    b = REAL["evidence_bundles"][0]
    if not (ROOT / b["path"] / "output/observation.json").exists():
        print("PRECONDITION UNMET: raw evidence is absent for", b["path"])
        print("Run tools/fetch-evidence.sh first.")
        return False
    return True


SPEC_FILES = ("tapefs-v1.md", "engine-api.md", "acceptance.md")


def _real_root(revision):
    for r in REAL["spec_bundle"]["roots"]:
        if r["revision"] == revision:
            return r["path"]
    return None


def _temp_root(tmp, name, source, files=SPEC_FILES, tamper=None):
    """A spec root outside the repository, copied from `source`."""
    d = pathlib.Path(tmp) / "roots" / name
    d.mkdir(parents=True, exist_ok=True)
    for f in files:
        data = (ROOT / source / f).read_bytes()
        if tamper == f:
            data += b"\n<!-- drift -->\n"
        (d / f).write_bytes(data)
    return str(d)


def spec_probes(tmp):
    d8_root = _real_root("DRAFT-8")
    base = copy.deepcopy(REAL["spec_bundle"])

    def with_roots(extra=(), drop=None, override=None):
        sb = copy.deepcopy(base)
        roots = [r for r in sb["roots"] if r["path"] != drop]
        if override:
            roots = [dict(r, revision=override[1]) if r["path"] == override[0] else r
                     for r in roots]
        sb["roots"] = roots + list(extra)
        return minimal(spec_bundle=sb)

    # green baseline: the untouched historical repository under the current
    # canonical bundle. Every red probe below differs from this in one fact.
    expect("green", "untouched historical roots under the current bundle",
           with_roots(), tmp)

    # A declared revision whose hashes VERSION.md repeats exactly, so the only
    # disagreement left is canonical spec/ bytes versus VERSION.md.
    sb = copy.deepcopy(base)
    sb["revisions"]["DRAFT-X"] = {f: "1" * 64 for f in SPEC_FILES}
    sb["manifest"] = _fake_version(tmp, "1", "DRAFT-X")
    expect("red", "canonical spec/ does not match spec/VERSION.md",
           minimal(spec_bundle=sb), tmp, "spec-bundle",
           contains="spec/tapefs-v1.md is ")

    expect("red", "spec/VERSION.md names a revision that is not declared",
           minimal(spec_bundle=dict(copy.deepcopy(base), manifest=_fake_version(tmp, None, "DRAFT-10"))),
           tmp, "spec-bundle", contains="bundle DRAFT-10 is not a declared")

    sb = copy.deepcopy(base)
    sb["revisions"]["DRAFT-8"].pop("acceptance.md")
    expect("red", "a declared revision is an incomplete hash triple",
           minimal(spec_bundle=sb), tmp, "spec-bundle",
           contains="revision DRAFT-8 is not a complete triple")

    expect("red", "a root declares an unknown bundle revision",
           with_roots(override=(d8_root, "DRAFT-7")), tmp, "spec-copies", contains='declares unknown bundle revision DRAFT-7')

    expect("red", "an embedded spec copy sits in an undeclared root",
           with_roots(drop=d8_root), tmp, "spec-copies", contains='but no bundle revision is declared for it')

    expect("red", "a DRAFT-8 copy sits in a DRAFT-9-declared root",
           with_roots(override=(d8_root, "DRAFT-9")), tmp, "spec-copies", contains='is the DRAFT-8 copy, but the root is declared DRAFT-9')

    d9 = _temp_root(tmp, "d9-as-d8", "spec")
    expect("red", "a DRAFT-9 copy sits in a DRAFT-8-declared root",
           with_roots(extra=[{"path": d9, "revision": "DRAFT-8"}]), tmp, "spec-copies", contains='is the DRAFT-9 copy, but the root is declared DRAFT-8')

    mixed = _temp_root(tmp, "mixed", d8_root)
    (pathlib.Path(mixed) / "engine-api.md").write_bytes((ROOT / "spec/engine-api.md").read_bytes())
    expect("red", "one root mixes revisions (no global either-hash acceptance)",
           with_roots(extra=[{"path": mixed, "revision": "DRAFT-8"}]), tmp, "spec-copies", contains='engine-api.md is the DRAFT-9 copy, but the root is declared DRAFT-8')

    part = _temp_root(tmp, "partial", "spec", files=SPEC_FILES[:2])
    expect("red", "a declared root is an incomplete triple",
           with_roots(extra=[{"path": part, "revision": "DRAFT-9"}]), tmp, "spec-copies", contains='is an incomplete triple: missing acceptance.md')

    drift = _temp_root(tmp, "drift", "spec", tamper="tapefs-v1.md")
    expect("red", "a copy drifts from its declared revision's hash",
           with_roots(extra=[{"path": drift, "revision": "DRAFT-9"}]), tmp, "spec-copies", contains='(hash drift)')

    expect("red", "a declared root does not exist",
           with_roots(extra=[{"path": str(pathlib.Path(tmp) / "absent"), "revision": "DRAFT-9"}]),
           tmp, "spec-copies", contains='does not exist')

    expect("red", "a root is declared twice",
           with_roots(extra=[{"path": d8_root, "revision": "DRAFT-8"}]), tmp, "spec-copies", contains='is declared more than once')

    # And the positive half of the migration: a correctly declared DRAFT-9
    # root is accepted alongside the untouched DRAFT-8 roots.
    good9 = _temp_root(tmp, "good-d9", "spec")
    expect("green", "a DRAFT-9 root declared DRAFT-9 beside DRAFT-8 roots",
           with_roots(extra=[{"path": good9, "revision": "DRAFT-9"}]), tmp)


def _fake_version(tmp, digit, revision):
    """A VERSION.md whose hashes are fake (digit) or the declared ones."""
    rows = []
    for f in SPEC_FILES:
        h = digit * 64 if digit else REAL["spec_bundle"]["revisions"]["DRAFT-9"][f]
        rows.append(f"| `spec/{f}` | {revision} | `{h}` |")
    p = pathlib.Path(tmp) / f"VERSION-{revision}-{digit}.md"
    p.write_text("| File | Revision | SHA-256 |\n|---|---|---|\n" + "\n".join(rows) + "\n",
                 encoding="utf-8")
    return str(p)


def main():
    global passed, failed
    if not check_preconditions():
        return 2
    print("== evidence integrity gate can go red ==")
    with tempfile.TemporaryDirectory() as tmp:
        # 1. subtree identity. HEAD is the base so unrelated package self-tests
        # are skipped; this probe tests only declaration versus observed tree.
        pkg = copy.deepcopy(REAL["packages"][0])
        pkg["tree"] = "0" * 40
        expect(
            "red", "declared subtree hash does not match HEAD",
            minimal(packages=[pkg]), tmp, "subtree",
        )

        # 2. package self-test failure. No base is supplied for this one probe,
        # forcing the declared self-test to execute.
        pkg = dict(REAL["packages"][0], selftest=["false"])
        expect(
            "red", "package self-test fails",
            minimal(packages=[pkg]), tmp, "selftest", base="",
        )

        # 3. replay outcome does not match the declaration. Exactly one retained
        # bundle is replayed instead of the entire manifest twice.
        bundle = dict(REAL["evidence_bundles"][0], expect="refuse")
        expect(
            "red", "bundle replays green where refusal is declared",
            minimal(evidence_bundles=[bundle]), tmp, "replay",
        )

        # 4. spec bundle and embedded copies (#248: bundle-version aware).
        # Every probe below starts from the real spec_bundle declaration and
        # changes exactly one fact. Temporary roots live outside the repo, so
        # no historical byte is touched.
        spec_probes(tmp)

        # 5. manifest adapter identity != observation adapter identity. Give the
        # bundle a tiny replay program whose declared refusal is satisfied, so
        # adapter identity is the only intentional failure in this probe.
        bundle_dir = pathlib.Path(tmp) / "bundle"
        (bundle_dir / "output").mkdir(parents=True)
        (bundle_dir / "manifest.json").write_text(
            json.dumps({"adapter": {"kind": "product", "id": "probe-v1"}}),
            encoding="utf-8",
        )
        (bundle_dir / "output/observation.json").write_text(
            json.dumps({"adapter": {"kind": "synthetic", "id": "probe-v1"}}),
            encoding="utf-8",
        )
        refuse = pathlib.Path(tmp) / "refuse.py"
        refuse.write_text("raise SystemExit(1)\n", encoding="utf-8")
        bundle = {
            "path": str(bundle_dir),
            "replay": str(refuse),
            "expect": "refuse",
            "why": "negative-control probe",
        }
        expect(
            "red", "adapter kind/ID disagree between manifest and observation",
            minimal(evidence_bundles=[bundle]), tmp, "adapter-id",
        )

    print(f"  {passed} passed, {failed} broken")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
