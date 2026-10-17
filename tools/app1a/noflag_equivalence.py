#!/usr/bin/env python3
"""APP-1A S1 (#452): Software's own equivalence and report-shape check for the
`--report` ingest candidate. It is not Verification's test and accepts nothing.

For each census case whose setup needs no test-build seam (no kill, fault, pause or
mutation environment), the inputs are built once per run by the packet transport's
own setup_case (host/ingest/stage1/run_packet.py) and run three ways:

  base     the AP4 candidate's shipping binary (6126d04), no report flags;
  noflag   this candidate's shipping binary, no report flags;
  report   this candidate with --report FILE --report-nonce N.

base vs noflag must agree byte for byte: exit, stdout, stderr and every published
file (paths normalized to the case's own work directory). report must agree with
noflag on exit, stdout, stderr and published bytes, and its report must be a
well-formed APP-1A record sequence whose end equals the exit, with exactly one
refusal record iff the exit is nonzero. The refusal ID distribution is printed.

  noflag_equivalence.py --package DIR --sources DIR --base BIN --new BIN --out FILE
                        [--max-seconds S] [--jobs N] [--only SUBSTR]
"""
import argparse, concurrent.futures as cf, hashlib, json, os, re, shutil, sys, tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "host" / "ingest" / "stage1"))
import run_packet as rp  # noqa: E402

NONCE = "0123456789abcdef0123456789abcdef"
IDS2 = set("""INGEST_USAGE INGEST_LENGTH_INVALID INGEST_TOO_LONG INGEST_RIFF_LIMIT FOLDER_SYMLINK
FOLDER_UNREADABLE FOLDER_NOT_FOLDER FOLDER_DUPLICATE FOLDER_EMPTY FOLDER_NAME_COLLISION
FOLDER_NAME_NOT_UNICODE ENTRY_SYMLINK ENTRY_NESTED_FOLDER ENTRY_NOT_REGULAR ENTRY_NAME_INVALID
SOURCE_PROTECTED SOURCE_NOT_AUDIO SOURCE_TOO_SHORT SOURCE_CHANGED SOURCE_NON_FINITE SOURCE_LEVEL
SOURCE_TRIM_UNSUPPORTED SOURCE_OUTSIDE_INGEST1 SOURCE_CORRUPT JOIN_PEAK JOINED_PEAK DEST_EXISTS
DEST_APPEARED DEST_NAME_INVALID""".split())
IDS1 = {"IO_SOURCE", "IO_FOLDER", "IO_DEST", "IO_MEMORY", "INTERNAL"}
STEPS = ["list", "decode", "convert", "write", "publish"]
KEYS = {"start": ["t", "tool", "version", "nonce"], "progress": ["t", "step", "done", "total"],
        "end": ["t", "exit"]}


def tree(d, w):
    out = {}
    if d.exists():
        for p in sorted(d.rglob("*")):
            if p.is_file():
                out[str(p.relative_to(d))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def norm(b, w):
    """Case output with its own work directory replaced, so two runs compare."""
    s = b.decode("utf-8", "replace")
    return s.replace(str(w), "<W>").replace(str(w).replace("\\", "/"), "<W>")


def run(binp, tail, w, extra=()):
    import subprocess
    p = subprocess.run([binp, *extra, *tail], capture_output=True, cwd=w)
    return p.returncode, norm(p.stdout, w), norm(p.stderr, w)


def check_report(path, code):
    """APP-1A §1/§4 shape. Returns (problems, refusal-record-or-None)."""
    bad, ref = [], None
    raw = Path(path).read_bytes()
    if not raw.endswith(b"\n"):
        bad.append("unterminated final line")
    lines = raw.decode("utf-8").split("\n")[:-1]
    recs = []
    for l in lines:
        if re.search(r'":\s|,\s', l):
            bad.append("insignificant whitespace")
        try:
            recs.append((json.loads(l), l))
        except ValueError:
            bad.append(f"not JSON: {l[:80]}")
            return bad, None
    if not recs or recs[0][0].get("t") != "start":
        bad.append("first record is not start")
    if not recs or recs[-1][0].get("t") != "end":
        bad.append("last record is not end")
    seen_steps = []
    for r, l in recs:
        t = r.get("t")
        if t in KEYS and list(r) != KEYS[t]:
            bad.append(f"{t} keys {list(r)}")
        if t == "start" and (r["tool"] != "ingest" or r["nonce"] != NONCE):
            bad.append("start tool/nonce")
        if t == "progress":
            if r["step"] not in STEPS:
                bad.append(f"unknown step {r['step']}")
            elif seen_steps and STEPS.index(r["step"]) < STEPS.index(seen_steps[-1][0]):
                bad.append("step order")
            elif seen_steps and seen_steps[-1][0] == r["step"] and r["done"] < seen_steps[-1][1]:
                bad.append("done decreased")
            if r["total"] and r["done"] > r["total"]:
                bad.append("done > total")
            if seen_steps and seen_steps[-1][0] == r["step"] and seen_steps[-1][2] not in (0, r["total"]):
                bad.append("total changed")
            if not seen_steps or seen_steps[-1][0] != r["step"]:
                if any(s[0] == r["step"] for s in seen_steps):
                    bad.append("step block not contiguous")
            seen_steps.append((r["step"], r["done"], r["total"]))
        if t == "refusal":
            if ref is not None:
                bad.append("two refusal records")
            ref = r
            if list(r)[:3] != ["t", "id", "subject"]:
                bad.append(f"refusal keys {list(r)}")
        if t not in ("start", "progress", "refusal", "end"):
            bad.append(f"unknown record {t}")
    if recs and recs[-1][0].get("exit") != code:
        bad.append(f"end exit {recs[-1][0].get('exit')} != {code}")
    if code == 0 and ref is not None:
        bad.append("refusal on success")
    if code != 0:
        if ref is None:
            bad.append("no refusal on failure")
        elif ref["id"] not in (IDS2 if code == 2 else IDS1):
            bad.append(f"ID {ref['id']} not closed for exit {code}")
    return bad, ref


def one(a, n, case):
    w = Path(tempfile.mkdtemp(dir=a.work))
    try:
        res = {"n": n, "id": case["id"]}
        outs = {}
        for mode in ("base", "noflag", "report"):
            m = w / mode
            m.mkdir()
            tail, dest, env, notes, cap = rp.setup_case(case, m, Path(a.sources) / "assets")
            if env:
                return None
            binp = a.base if mode == "base" else a.new
            extra = ("--report", str(w / "report.jsonl"), "--report-nonce", NONCE) if mode == "report" else ()
            code, out, err = run(binp, tail, m, extra)
            outs[mode] = (code, out.replace("<W>", "<M>"), err.replace("<W>", "<M>"), tree(dest, m))
        b, f, r = outs["base"], outs["noflag"], outs["report"]
        res["exit"] = b[0]
        res["noflag_identical"] = b == f
        res["report_same_outputs"] = f == r
        if not res["noflag_identical"]:
            res["diff"] = {k: [b[i], f[i]] for i, k in enumerate(("exit", "stdout", "stderr", "dest")) if b[i] != f[i]}
        if not res["report_same_outputs"]:
            res["report_diff"] = {k: [f[i], r[i]] for i, k in enumerate(("exit", "stdout", "stderr", "dest")) if f[i] != r[i]}
        problems, ref = check_report(w / "report.jsonl", r[0])
        res["report_problems"] = problems
        if ref:
            res["refusal"] = ref
        return res
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
    a.work = a.work or tempfile.mkdtemp(prefix="app1a-eq-")
    os.makedirs(a.work, exist_ok=True)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    census = json.loads(Path(a.package, "CENSUS.json").read_text(encoding="utf-8"))["cases"]
    todo = [(n, c) for n, c in enumerate(census)
            if c["seconds"] <= a.max_seconds and (not a.only or a.only in c["id"]) and not c.get("scenario") in
            ("kill", "write-error", "mutation", "concurrent-dest")]
    results = []
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for r in ex.map(lambda x: one(a, *x), todo):
            if r is not None:
                results.append(r)
    ids = Counter((r["exit"], r["refusal"]["id"]) for r in results if "refusal" in r)
    summary = {
        "base_sha256": rp.sha_file(a.base), "new_sha256": rp.sha_file(a.new),
        "cases_run": len(results), "census_cases": len(census),
        "skipped_seam_or_long": len(census) - len(results),
        "noflag_identical": sum(r["noflag_identical"] for r in results),
        "report_same_outputs": sum(r["report_same_outputs"] for r in results),
        "report_wellformed": sum(not r["report_problems"] for r in results),
        "exit_counts": dict(Counter(str(r["exit"]) for r in results)),
        "refusal_ids": {f"{e}:{i}": n for (e, i), n in sorted(ids.items())},
        "failures": [r for r in results if not r["noflag_identical"] or not r["report_same_outputs"]
                     or r["report_problems"]][:50],
    }
    Path(a.out).write_text(json.dumps({"summary": summary, "results": results}, indent=1, sort_keys=True))
    print(json.dumps({k: v for k, v in summary.items() if k != "failures"}, indent=1))
    for f in summary["failures"][:20]:
        print("FAIL", f["n"], f["id"], {k: f.get(k) for k in ("diff", "report_diff", "report_problems")})
    ok = summary["noflag_identical"] == summary["report_same_outputs"] == summary["report_wellformed"] == len(results)
    sys.exit(0 if ok and results else 1)


if __name__ == "__main__":
    main()
