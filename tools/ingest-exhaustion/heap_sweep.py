#!/usr/bin/env python3
"""#457: deterministic allocation-failure stress of the TEST build (feature `observe`),
census case 1926 (resources/exhaustion). Software's own check; it judges nothing and
makes no shipping claim (the shipping claim is shipping_exhaustion.py's OS limits).

The test build's capped allocator (INGEST_HEAP_LIMIT, observe.rs) refuses any request
past a live-heap cap, exactly as the system allocator refuses one when memory runs out.
Swept in small steps, the cap lands the refusal on a different allocation each time:
input-sized buffers, decoder state, manifest strings, the error path. At every cap the
run must end in exit 0 with the unlimited run's bytes, or in exit 1 with the tool's own
out-of-memory diagnostic and nothing left behind. Anything else (std's abort on an
infallible allocation, a crash, a dirty exit 1) is a violation; --gate exits 1 on any.

Each transition between two caps that end differently is then re-swept every
`--refine` bytes, so the narrow windows where a large allocation succeeds and the next
small one is refused are hit too.

The uncorrected test build (6126d04's) is the negative control: CI requires the gate to
go red on it.

  heap_sweep.py --package DIR --sources DIR --bin OBSERVE_BUILD --out FILE
                [--from KIB] [--to KIB] [--step KIB] [--refine BYTES] [--gate]
"""
import argparse, json, os, shutil, subprocess, sys, tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "host" / "ingest" / "stage1"))
import run_packet as rp  # noqa: E402


def one(binp, case, assets, limit):
    w = Path(tempfile.mkdtemp(prefix="heap-"))
    try:
        tail, dest, env, notes, cap = rp.setup_case(case, w, assets)
        assert not env, env
        unrel = rp.sha_file(dest.parent / "unrelated.txt")
        obs = w / "observe"
        obs.mkdir()
        e = dict(os.environ, INGEST_OBSERVE_DIR=str(obs))
        if limit is not None:
            e["INGEST_HEAP_LIMIT"] = str(limit)
        p = subprocess.run([binp] + tail, capture_output=True, env=e)
        stage = "." + dest.name + ".ingest-stage-"
        r = {"limit": limit, "exit": p.returncode, "stderr": p.stderr[:400].decode("utf-8", "replace"),
             "dest_exists": dest.exists(),
             "owned_stage_left": sorted(x.name for x in dest.parent.iterdir() if x.name.startswith(stage)),
             "out_dir_entries": sorted(x.name for x in dest.parent.iterdir()),
             "unrelated_unchanged": rp.sha_file(dest.parent / "unrelated.txt") == unrel}
        if p.returncode == 0 and dest.exists():
            r["published"] = {k: rp.sha_file(dest / k) for k in ("audio.wav", "manifest.json")}
        return r
    finally:
        shutil.rmtree(w, ignore_errors=True)


def violation(r, pos):
    if r["exit"] == 0:
        return None if r.get("published") == pos.get("published") else "exit 0 without the unlimited run's bytes"
    if r["exit"] == 1:
        clean = (not r["dest_exists"] and not r["owned_stage_left"] and r["unrelated_unchanged"]
                 and r["out_dir_entries"] == ["unrelated.txt"])
        own = r["stderr"].startswith("ingest:") and "out of memory" in r["stderr"]
        return None if clean and own else "exit 1 without own diagnostic or not clean"
    return f"ended {r['exit']}: {r['stderr'][:100]!r}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", required=True)
    ap.add_argument("--sources", required=True)
    ap.add_argument("--bin", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--from", dest="lo", type=int, default=32)
    ap.add_argument("--to", dest="hi", type=int, default=12288)
    ap.add_argument("--step", type=int, default=32)
    ap.add_argument("--refine", type=int, default=256)
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    binp = os.path.abspath(a.bin)
    census = json.loads(Path(a.package, "CENSUS.json").read_text(encoding="utf-8"))["cases"]
    case = next(c for c in census if c["id"] == "resources/exhaustion")
    assets = Path(a.sources) / "assets"
    pos = one(binp, case, assets, None)
    rows = [one(binp, case, assets, k * 1024) for k in range(a.lo, a.hi + 1, a.step)]
    end = lambda r: (r["exit"], r["stderr"].split("\n")[0])
    fine = []
    for x, y in zip(rows, rows[1:]):
        if end(x) != end(y):
            fine += [one(binp, case, assets, n) for n in range(x["limit"] + a.refine, y["limit"], a.refine)]
    rows = sorted(rows + fine, key=lambda r: r["limit"])
    viol = [{"limit": r["limit"], "why": v} for r in rows if (v := violation(r, pos))]
    if pos["exit"] != 0:
        viol.append({"limit": None, "why": f"unlimited positive ended {pos['exit']}"})
    ends = Counter(("published" if r["exit"] == 0 else r["stderr"].split("\n")[0][:90]) for r in rows)
    res = {"binary_sha256": rp.sha_file(binp), "case": case["id"], "positive": pos, "rows": rows,
           "ends": dict(ends), "violations": viol}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_bytes(rp.canonical(res))
    print(json.dumps({"binary_sha256": res["binary_sha256"], "caps": len(rows), "ends": res["ends"],
                      "violations": len(viol), "first_violations": viol[:5]}, indent=1))
    if a.gate:
        print("GATE RED" if viol else "GATE GREEN")
        sys.exit(1 if viol else 0)


if __name__ == "__main__":
    main()
