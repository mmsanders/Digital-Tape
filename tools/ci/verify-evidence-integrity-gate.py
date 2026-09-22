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


def expect(want, name, manifest_obj, tmp, saying=None, base="HEAD"):
    global passed, failed
    rc, out = run_gate(manifest_obj, tmp, base=base)
    red = rc != 0
    good = (want == "red" and red) or (want == "green" and not red)
    if good and saying and want == "red" and f"[{saying}]" not in out:
        good = False
        why = f"went red but never named [{saying}]"
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

        # 4. a spec copy that does not match the bundle manifest.
        fake_ver = pathlib.Path(tmp) / "VERSION.md"
        fake_ver.write_text(
            "| File | Revision | SHA-256 |\n|---|---|---|\n"
            "| `spec/tapefs-v1.md` | DRAFT-8 | `" + "1" * 64 + "` |\n"
            "| `spec/engine-api.md` | DRAFT-8 | `" + "2" * 64 + "` |\n"
            "| `spec/acceptance.md` | DRAFT-8 | `" + "3" * 64 + "` |\n",
            encoding="utf-8",
        )
        spec = copy.deepcopy(REAL["spec_bundle"])
        spec["manifest"] = str(fake_ver)
        expect(
            "red", "spec copy does not match the bundle manifest",
            minimal(spec_bundle=spec), tmp, "spec-copies",
        )

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
