#!/usr/bin/env python3
"""Negative control for the current-engine regression gate on accepted bindings.

PM ruling (#320): the four independently accepted Software bindings no longer pin
HEAD's engine/ tree. Instead each runner requires
  (a) the retained provenance (build-identity.json) still names the accepted engine,
  (b) a fresh build on the current engine/ regenerates observations byte-identical
      to the retained, accepted observations (run_product.py --retained).

A gate that never goes red has not established what it detects. For every
binding this script copies the retained evidence to a scratch directory, makes
ONE change, re-seals SHA256SUMS so the committed-hash check still passes (the
failure must come from the gate itself, not from a checksum), and requires
run_product.py --retained to fail with the gate's own message:

  observation   one byte of one retained observation changed      -> (b) red
  provenance    retained build-identity names a different engine  -> (a) red

The unmodified retained evidence must pass. Adapters and engine must already be
built. Exits non-zero if any control survives or any baseline fails.
"""
from __future__ import annotations

import gzip
import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BINDINGS = {
    "crossrun_wp08_adapter": "p1-r46-product",
    "history_wp09_adapter": "p1-r46-product",
    "sequential_wp06_adapter": "p1-r48-product",
    "capacity_wp09_adapter": "p1-r53-product",
}
OBSERVATION_RED = "differs from the committed retained evidence"
PROVENANCE_RED = "retained provenance names engine"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reseal(d: Path, name: str) -> None:
    lines = []
    for line in (d / "SHA256SUMS").read_text().splitlines():
        digest, n = line.split(None, 1)
        if n.lstrip("*") == name:
            digest = sha((d / name).read_bytes())
        lines.append(f"{digest}  {n}")
    (d / "SHA256SUMS").write_text("\n".join(lines) + "\n", newline="\n")


def flip(raw: bytes) -> bytes:
    """Change one byte inside the first JSON string value of the first record."""
    i = raw.index(b'":"') + 3
    return raw[:i] + (b"0" if raw[i:i + 1] != b"0" else b"1") + raw[i + 1:]


def mutate_observation(d: Path) -> None:
    gz = d / "observations.jsonl.gz"
    if gz.exists():
        raw = flip(gzip.decompress(gz.read_bytes()))
        gz.write_bytes(gzip.compress(raw, 9, mtime=0))
        sums = (d / "SHA256SUMS").read_text().splitlines()
        (d / "SHA256SUMS").write_text("".join(
            (f"{sha(raw)}  observations.jsonl" if l.split(None, 1)[1].lstrip("*") == "observations.jsonl"
             else l) + "\n" for l in sums), newline="\n")
        reseal(d, "observations.jsonl.gz")
    else:
        p = d / "observations.jsonl"
        p.write_bytes(flip(p.read_bytes()))
        reseal(d, "observations.jsonl")


def mutate_provenance(d: Path) -> None:
    p = d / "build-identity.json"
    ident = json.loads(p.read_text())
    ident["engine_tree"] = "0" * 40
    p.write_text(json.dumps(ident, indent=2, sort_keys=True) + "\n", newline="\n")
    reseal(d, "build-identity.json")


def run(binding: str, retained: Path, scratch: Path) -> tuple[int, str]:
    out = scratch / ("out-" + retained.name)
    r = subprocess.run([sys.executable, str(ROOT / "tests" / binding / "run_product.py"),
                        "--evidence", str(out), "--retained", str(retained)],
                       capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode, r.stdout + r.stderr


def epoch_controls(binding, scratch):
    spec = importlib.util.spec_from_file_location("epoch", ROOT / "tests/playback_regression_epoch/check.py")
    epoch = importlib.util.module_from_spec(spec); spec.loader.exec_module(epoch)
    suite = {"history_wp09_adapter":"history-wp09-package", "capacity_wp09_adapter":"capacity-wp09-package"}[binding]
    out = scratch / binding / "epoch-baseline"
    r = subprocess.run([sys.executable,"-B",ROOT/"tools/readopt-binding.py","--suite",suite,"--out",out],capture_output=True,text=True)
    print(r.stdout+r.stderr)
    if r.returncode:return [binding+": baseline did not pass"]
    print("baseline ok ",binding)
    selection = epoch.select(ROOT,suite)
    data = (out/"fresh/observations.jsonl").read_bytes()
    altered = out/"altered.jsonl";altered.write_bytes(flip(data))
    bad=[]
    try:
        epoch.regenerate(altered,suite,selection)
        bad.append(binding+" observation");print("SURVIVED",binding,"observation")
    except AssertionError as e:
        if str(e)!="exact regenerated raw stream":raise
        print("killed",binding,"observation:",e)
    retained = scratch / binding / "altered-old-provenance"
    src = ROOT / epoch.load()["suites"][suite]["old"]["path"]
    shutil.copytree(src,retained);mutate_provenance(retained)
    try:
        epoch.authenticate(suite,retained,"old")
        bad.append(binding+" provenance");print("SURVIVED",binding,"provenance")
    except AssertionError as e:
        if "old archive/file identity" not in str(e):raise
        print("killed",binding,"provenance:",e)
    return bad


def main() -> int:
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        for binding, ev in BINDINGS.items():
            if binding in ("history_wp09_adapter", "capacity_wp09_adapter"):
                bad.extend(epoch_controls(binding, scratch))
                continue
            src = ROOT / "tests" / binding / "evidence" / ev
            rc, log = run(binding, src, scratch / binding / "baseline")
            if rc != 0 or "byte-identical" not in log:
                bad.append(f"{binding}: baseline did not pass")
                print(f"BASELINE FAIL {binding}\n{log}")
                continue
            print(f"baseline ok  {binding}")
            for label, mutate, expect in (("observation", mutate_observation, OBSERVATION_RED),
                                          ("provenance", mutate_provenance, PROVENANCE_RED)):
                d = scratch / binding / label / ev
                shutil.copytree(src, d)
                mutate(d)
                rc, log = run(binding, d, scratch / binding / label)
                if rc != 0 and expect in log:
                    print(f"killed       {binding} {label}: {expect}")
                else:
                    bad.append(f"{binding} {label}")
                    print(f"SURVIVED     {binding} {label} (rc={rc})\n{log}")
    total = 2 * len(BINDINGS)
    print(f"{total - sum(1 for b in bad if 'baseline' not in b)}/{total} regression-gate controls killed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
