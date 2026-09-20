#!/usr/bin/env python3
"""Negative control for the evidence integrity gate.

CLAUDE.md §1: "Every new gate needs a real negative control: a gate that never
goes red has not established what it detects." This plants one violation per
check, asserts the gate goes red naming that check, and asserts it is green
again once removed.

It mutates NO real file and NO git state. Every probe is a doctored copy of the
manifest in a temp directory, fed to the gate through EVIDENCE_MANIFEST. That
is deliberate: an earlier negative control in this repository unwound a probe
with `git reset --hard` and destroyed an unrelated commit.

What this establishes, honestly stated: that each check compares the declared
value against the observed one and fails on a mismatch. Check 1 reads the tree
from HEAD, so the probe doctors the declared side rather than committing a
tampered tree -- the comparison proven is the same one either way, but a
committed-tamper test would need a scratch worktree and is not done here.
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


def run_gate(manifest_obj, tmp):
    p = pathlib.Path(tmp) / "IMPORTS.json"
    p.write_text(json.dumps(manifest_obj), encoding="utf-8")
    env = dict(os.environ, EVIDENCE_MANIFEST=str(p))
    r = subprocess.run([sys.executable, str(GATE)], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def expect(want, name, manifest_obj, tmp, saying=None):
    global passed, failed
    rc, out = run_gate(manifest_obj, tmp)
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


def main():
    global passed, failed
    print("== evidence integrity gate can go red ==")
    with tempfile.TemporaryDirectory() as tmp:
        expect("green", "baseline, real manifest", REAL, tmp)

        # 1. subtree identity: declare a tree that is not what HEAD holds.
        m = copy.deepcopy(REAL)
        m["packages"][0]["tree"] = "0" * 40
        expect("red", "declared subtree hash does not match HEAD", m, tmp, "subtree")

        # 2. package self-test failure.
        m = copy.deepcopy(REAL)
        m["packages"] = [dict(REAL["packages"][0], selftest=["false"])]
        m["evidence_bundles"] = []
        expect("red", "package self-test fails", m, tmp, "selftest")

        # 3. replay outcome does not match the declaration.
        m = copy.deepcopy(REAL)
        m["packages"] = []
        m["evidence_bundles"] = [dict(REAL["evidence_bundles"][0], expect="refuse")]
        expect("red", "bundle replays green where refusal is declared", m, tmp, "replay")

        # 4. a spec copy that does not match the bundle manifest.
        fake_ver = pathlib.Path(tmp) / "VERSION.md"
        fake_ver.write_text(
            "| File | Revision | SHA-256 |\n|---|---|---|\n"
            "| `spec/tapefs-v1.md` | DRAFT-8 | `" + "1" * 64 + "` |\n"
            "| `spec/engine-api.md` | DRAFT-8 | `" + "2" * 64 + "` |\n"
            "| `spec/acceptance.md` | DRAFT-8 | `" + "3" * 64 + "` |\n",
            encoding="utf-8")
        m = copy.deepcopy(REAL)
        m["packages"] = []
        m["evidence_bundles"] = []
        m["spec_bundle"]["manifest"] = str(fake_ver)
        expect("red", "spec copy does not match the bundle manifest", m, tmp, "spec-copies")

        # 5. manifest adapter identity != observation adapter identity.
        bundle = pathlib.Path(tmp) / "bundle"
        (bundle / "output").mkdir(parents=True)
        (bundle / "manifest.json").write_text(
            json.dumps({"adapter": {"kind": "product", "id": "probe-v1"}}), encoding="utf-8")
        (bundle / "output/observation.json").write_text(
            json.dumps({"adapter": {"kind": "synthetic", "id": "probe-v1"}}), encoding="utf-8")
        m = copy.deepcopy(REAL)
        m["packages"] = []
        m["evidence_bundles"] = [{"path": str(bundle), "replay": "tests/playback_complete_draft8/replay.py",
                                  "expect": "refuse", "why": "probe"}]
        expect("red", "adapter kind/ID disagree between manifest and observation", m, tmp, "adapter-id")

        expect("green", "real manifest still green afterwards", REAL, tmp)

    print(f"  {passed} passed, {failed} broken")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
