#!/usr/bin/env python3
"""#457: Software's own equivalence check of the exhaustion correction against the
submitted AP4 candidate 6126d04. It is not Verification's test and accepts nothing.

Every census case whose setup needs no test-build seam (no kill, fault, pause or
mutation environment) and is at most `--max-seconds` long is built by the packet
transport's own setup_case (host/ingest/stage1/run_packet.py) and run by both shipping
binaries. They must agree byte for byte on exit, stdout, stderr and every published
file, with one disclosed exception, the mandatory new version (0.1.0 -> 0.1.1):
manifest.json's `tool_version` and the `--version` line are compared after replacing
the new value with the base's. audio.wav is never normalized.

  equivalence.py --package DIR --sources DIR --base BIN --new BIN --out FILE
                 [--max-seconds S] [--jobs N] [--only SUBSTR]
"""
import argparse, concurrent.futures as cf, hashlib, json, os, shutil, subprocess, sys, tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "host" / "ingest" / "stage1"))
import run_packet as rp  # noqa: E402


def version(binp):
    return subprocess.run([binp, "--version"], capture_output=True, text=True).stdout.split()[1]


def tree(d, swap):
    out = {}
    if d.exists():
        for p in sorted(d.rglob("*")):
            if p.is_file():
                b = p.read_bytes()
                if p.name == "manifest.json" and swap:
                    b = b.replace(swap[0], swap[1])
                out[p.relative_to(d).as_posix()] = hashlib.sha256(b).hexdigest()
    return out


def one(a, n, case):
    w = Path(tempfile.mkdtemp(dir=a.work))
    try:
        outs = {}
        for mode, binp in (("base", a.base), ("new", a.new)):
            m = w / mode
            m.mkdir()
            tail, dest, env, notes, cap = rp.setup_case(case, m, Path(a.sources) / "assets")
            if env:
                return None
            p = subprocess.run([binp, *tail], capture_output=True, cwd=m)
            norm = lambda b: b.decode("utf-8", "replace").replace(str(m), "<M>").replace(str(m).replace("\\", "/"), "<M>")
            swap = None if mode == "base" else (a.swap_new, a.swap_base)
            out = norm(p.stdout)
            if swap:
                out = out.replace(f"ingest {a.vn} INGEST-1 ", f"ingest {a.vb} INGEST-1 ")
            outs[mode] = (p.returncode, out, norm(p.stderr), tree(dest, swap))
        b, f = outs["base"], outs["new"]
        r = {"n": n, "id": case["id"], "exit": b[0], "identical": b == f}
        if not r["identical"]:
            r["diff"] = {k: [b[i], f[i]] for i, k in enumerate(("exit", "stdout", "stderr", "dest")) if b[i] != f[i]}
        return r
    finally:
        shutil.rmtree(w, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", required=True)
    ap.add_argument("--sources", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", default=None)
    ap.add_argument("--max-seconds", type=int, default=3600)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    a.base, a.new = os.path.abspath(a.base), os.path.abspath(a.new)
    vb, vn = a.vb, a.vn = version(a.base), version(a.new)
    a.swap_base = f'"tool_version":"{vb}"'.encode()
    a.swap_new = f'"tool_version":"{vn}"'.encode()
    a.work = a.work or tempfile.mkdtemp(prefix="exh-eq-")
    os.makedirs(a.work, exist_ok=True)
    census = json.loads(Path(a.package, "CENSUS.json").read_text(encoding="utf-8"))["cases"]
    todo = [(n, c) for n, c in enumerate(census)
            if c["seconds"] <= a.max_seconds and (not a.only or a.only in c["id"])
            and c.get("scenario") not in ("kill", "write-error", "mutation", "concurrent-dest")]
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        results = [r for r in ex.map(lambda x: one(a, *x), todo) if r is not None]
    summary = {
        "base_sha256": rp.sha_file(a.base), "new_sha256": rp.sha_file(a.new),
        "base_version": vb, "new_version": vn, "normalized": "manifest.json tool_version and the --version line only",
        "cases_run": len(results), "census_cases": len(census),
        "skipped_seam_or_long": len(census) - len(results),
        "identical": sum(r["identical"] for r in results),
        "exit_counts": dict(Counter(str(r["exit"]) for r in results)),
        "failures": [r for r in results if not r["identical"]][:50],
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"summary": summary, "results": results}, indent=1, sort_keys=True))
    print(json.dumps({k: v for k, v in summary.items() if k != "failures"}, indent=1))
    for f in summary["failures"][:20]:
        print("FAIL", f["n"], f["id"], f.get("diff"))
    sys.exit(0 if results and summary["identical"] == len(results) else 1)


if __name__ == "__main__":
    main()
