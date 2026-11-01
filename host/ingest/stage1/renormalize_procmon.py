#!/usr/bin/env python3
"""Re-normalize a Procmon packet offline from its retained session files.

The packet keeps the complete capture (observer-session/session.pml.gz and
session.csv.gz, each with its SHA-256). This re-reads them with the current
observers.Procmon, re-attributes every native record to its process instance,
re-extracts its raw trace and re-applies the integrity checks. It never edits
the input packet: results go to --out as a separate, hash-bound overlay.

Instance binding: each record is bound to the one ingest.exe instance whose
Process Start command line is exactly its recorded argv (subprocess.list2cmdline,
as launched); a record with no such unique instance stays unbound and incomplete.
The observe directory is the one its .mark paths name.

usage: renormalize_procmon.py PACKET --out DIR
"""
import argparse, gzip, json, ntpath, re, shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import observers  # noqa: E402


def gunzip(src, dst, want):
    with gzip.open(src, "rb") as a, open(dst, "wb") as b:
        shutil.copyfileobj(a, b)
    got = observers.sha_file(dst)
    if want and got != want:
        sys.exit(f"{src}: inflated sha256 {got} != recorded {want}")
    return got


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("packet")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    root, out = Path(a.packet), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sess = root / "observer-session"
    pm = observers.Procmon.__new__(observers.Procmon)
    pm.session = out
    pm.pml, pm.csv = out / "session.pml", out / "session.csv"
    hashes = {}
    for name in ("pml", "csv"):
        want = (sess / f"session.{name}.sha256").read_text().split()[0] if (sess / f"session.{name}.sha256").exists() else None
        hashes[name] = gunzip(sess / f"session.{name}.gz", out / f"session.{name}", want)
    pm._load()
    col = pm.col
    by_cmd = {}
    for x in pm.instances:
        m = re.search(r"Command line: (.*?), Current directory: ", x["detail"])
        if m and x["name"].lower() == "ingest.exe":
            by_cmd.setdefault(m.group(1), []).append(x)
    owners, results = {}, {}
    natives = sorted(root.glob("cases/*/native.json")) + sorted(root.glob("cases/*/comparisons/*/native.json"))
    for nat in natives:
        rel = nat.relative_to(root).as_posix()
        d = json.loads(nat.read_text(encoding="utf-8"))
        if d.get("unavailable"):
            continue
        b = d.get("session_binding")
        cands = by_cmd.get(subprocess.list2cmdline(d.get("argv") or []), [])
        insts = pm._with_children(cands) if len(cands) == 1 else []
        rows = [i for x in insts for i in x["rows"]]
        argv = d.get("argv") or []
        dest = argv[argv.index("--out") + 1] if "--out" in argv else (b or {}).get("dest", "")
        marks = [observers.MARK.search(pm.rows[i][col["Path"]]) for i in rows]
        markpath = next((pm.rows[i][col["Path"]] for i, m in zip(rows, marks) if m), None)
        obs = next((m.group(1) for m in (re.match(r"^(.*\\obs-[a-z-]+)\\", pm.rows[i][col["Path"]]) for i in rows) if m), None)
        obsdir = ((b or {}).get("obsdir") or (ntpath.dirname(ntpath.dirname(markpath)) if markpath else None)
                  or obs or "<no observe directory seen>")
        stage_prefix = "." + ntpath.basename(dest) + ".ingest-stage-" if dest else "<no dest>"
        dst = out / rel.replace("native.json", "trace.txt")
        dst.parent.mkdir(parents=True, exist_ok=True)
        idx = pm.extract(dst, insts)
        owners[rel] = idx
        events, failed, completion, checks = pm.normalize(dst, dest, stage_prefix, obsdir, d.get("seam_events", []),
                                                         {"instances": insts})
        new = dict(d, events=events, failed_ops=failed, process_completion=completion, integrity=checks,
                   complete=completion is not None and all(checks.values()), raw_trace_sha256=observers.sha_file(dst),
                   session_record_indices=idx, renormalized_from=rel)
        (out / rel).write_bytes(observers.canonical(new))
        results[rel] = {"complete": new["complete"], "failed_checks": [k for k, v in checks.items() if not v],
                        "events_before": [e["op"] for e in d.get("events", [])], "events_after": [e["op"] for e in events]}
    # the session's other owners: the selftest and the shipping reruns (by Process Start command line)
    st = [x for x in pm.instances if x["name"].lower().startswith("probe-")]
    owners["observer-selftest"] = [i for x in st for i in x["rows"]]
    claimed = {i for v in owners.values() for i in v}
    for n, x in enumerate(pm.instances):  # shipping reruns and any other ingest.exe launch
        if x["rows"] and x["rows"][0] not in claimed and x["name"].lower() == "ingest.exe":
            owners[f"other-ingest-instance-{n}"] = x["rows"]
    part = pm.partition(owners)
    summary = {
        "packet": str(root), "session_sha256": hashes, "alignment": pm.align,
        "partition": {k: part[k] for k in ("records", "owned", "unowned_count", "multiply_owned")},
        "natives": len(results), "complete": sum(r["complete"] for r in results.values()),
        "incomplete": {k: r["failed_checks"] for k, r in results.items() if not r["complete"]},
        "events_changed": sum(r["events_before"] != r["events_after"] for r in results.values()),
        "note": "Software re-normalization of retained raw session files; not a review, receipt or PASS.",
    }
    (out / "RENORMALIZED.json").write_bytes(observers.canonical(dict(summary, results=results)))
    for k in ("session.pml", "session.csv"):
        (out / k).unlink()
    print(json.dumps({k: v for k, v in summary.items() if k != "incomplete"}, indent=1))
    for k, v in list(summary["incomplete"].items())[:20]:
        print("INCOMPLETE", k, v)


if __name__ == "__main__":
    main()
