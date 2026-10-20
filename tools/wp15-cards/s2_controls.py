#!/usr/bin/env python3
"""S2 producer controls for Verification #208 correction round 1 (#465).

Runs the real platform enumerator through `tapectl-test discover` (every listed
disk, every fact as the enumerator produced it, and the policy verdict) and
`tapectl-test cards` (exit status and summary) once per case, and records the
raw stdout, stderr and exit status of each run in CONTROLS.json.

A case is NAME=FAULTS. FAULTS is empty for a native observation, or a
comma-separated TAPECTL_TEST_DISC_FAULT list: the named OS queries are treated
as failed by the real enumerator inside tapectl-test. Those rows are compiled
controls (an injected query failure in a test build), not native observations
of an OS failing. The first case is the neighbour the others are compared
with; the comparison printed here is a reading aid, not a verdict.

Optional --old TAPECTL_TEST runs the same native cases with an earlier
producer, for a before/after comparison on the same machine state.
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(binary, args, faults):
    env = dict(os.environ)
    env.pop("TAPECTL_TEST_CARDS", None)
    env.pop("TAPECTL_TEST_CARDS_VECTOR", None)
    env.pop("TAPECTL_TEST_DISC_FAULT", None)
    if faults:
        env["TAPECTL_TEST_DISC_FAULT"] = faults
    p = subprocess.run([binary] + args, env=env, capture_output=True, timeout=120)
    return {"argv": [Path(binary).name] + args, "exit": p.returncode,
            "stdout": p.stdout.decode("utf-8", "replace"), "stderr": p.stderr.decode("utf-8", "replace")}


def disks(discover):
    out = {}
    for line in discover["stdout"].splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        out[d["path"]] = d
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tapectl-test", required=True)
    ap.add_argument("--old", help="an earlier tapectl-test, run on the native cases only")
    ap.add_argument("--old-source", default="")
    ap.add_argument("--source", default="")
    ap.add_argument("--state", required=True, help="a label for the machine state these cases ran in")
    ap.add_argument("--out", required=True)
    ap.add_argument("case", nargs="+", help="NAME=FAULTS")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    bins = [("new", a.tapectl_test, a.source)] + ([("old", a.old, a.old_source)] if a.old else [])
    for which, binary, source in bins:
        for spec in a.case:
            name, _, faults = spec.partition("=")
            if which == "old" and faults:
                continue
            row = {"case": name, "producer": which, "source": source, "binary_sha256": sha256(binary),
                   "faults": faults or None,
                   "kind": "compiled control (injected OS-query failure in tapectl-test)" if faults else "native observation",
                   "discover": run(binary, ["discover"], faults), "cards": run(binary, ["cards"], faults)}
            rows.append(row)
    base = disks(rows[0]["discover"])
    for row in rows:
        now = disks(row["discover"])
        diff = []
        for path in sorted(set(base) | set(now)):
            b, n = base.get(path), now.get(path)
            if b is None or n is None:
                diff.append({"path": path, "listed": [b is not None, n is not None]})
                continue
            changed = {k: [b[k], n[k]] for k in n if k not in ("disk", "of") and b.get(k) != n[k]}
            if changed:
                diff.append({"path": path, "changed": changed})
        row["against_first_case"] = diff
        print(f"{a.state} {row['producer']} {row['case']}: discover exit {row['discover']['exit']}, "
              f"cards exit {row['cards']['exit']} {row['cards']['stdout'].strip().splitlines()[-1:] or row['cards']['stderr'].strip()}",
              flush=True)
        for d in diff:
            print("   ", json.dumps(d), flush=True)
    doc = {"state": a.state, "platform": platform.platform(), "rows": rows}
    (out / f"CONTROLS-{a.state}.json").write_text(json.dumps(doc, indent=1))


if __name__ == "__main__":
    sys.exit(main())
