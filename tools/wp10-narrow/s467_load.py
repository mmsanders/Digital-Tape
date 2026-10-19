#!/usr/bin/env python3
"""#467 Tier 2: actual selected host-load faults and per-command fresh-input rows, for
Verification #210 (tests/wp10_narrow_supplement_r1/ADAPTER.md §2). Software transports
raw facts; Verification judges them. No engine change, no shipping change.

    python3 -B tools/wp10-narrow/s467_load.py --retained DIR --out DIR

The route is the existing host load binding (tests/wp10_subset_binding/run_load.py:
tapectl-test load of the golden voice.wav onto the fixed provisioned image). The faults
are the test seam's `write-error:N` (port write N of the process is a real failed OS
write on an invalidated handle: nothing of it lands) and `flush-error:N` (only barrier N
is a real failed OS barrier), both compiled only into tapectl-test. N is the write call /
barrier ordinal in the trace's own order, the same ordinals HOST-LOAD-PLAN.json counts.

Faults: the licensed pilot only (writes 0, 7, 8, 352; barriers 1, 26, 51), with a no-fault
positive and the existing native-flush-error (every barrier fails; barrier 0 first) as
route controls. Each run starts from its own copy of the pristine provisioned image; the
failed run's image is then remounted by verify / dump A / dump B, each a fresh process on
its own copy (run_load.remount, unchanged).

Command rows: from the retained corrected load0 rows (--retained: the unzipped
retained-load0.zip), the unique remounted projections sorted by hash; the first of each
(side A, side B) rendered-audio state and every projection a command reported
needs_repair for. Each is rebuilt from the retained initial image, trace and landing order
with the binding's own replay/projection code and checked against its hash, then
remounted again in fresh processes with every command's full seam trace retained.
Projections stay projections: they are not interrupted executions.

Writes BUNDLE.json (fields per oracle.py) and COST.json (actual CPU and bytes).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import resource
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "wp10_subset_binding"))
import run_load as rl  # noqa: E402
import subset_driver as sd  # noqa: E402

PLAN = json.loads((ROOT / "tests/wp10_narrow_supplement_r1/HOST-LOAD-PLAN.json").read_text())
PILOT = [(p["kind"], p["ordinal"]) for p in PLAN["licensed_pilot"]]
CONTROLS = [("none", None), ("native-flush-error", None)]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def events(seam: dict) -> list[dict]:
    """Every port write call and barrier of the run, by ordinal, as the seam recorded it."""
    out, w, f = [], 0, 0
    for e in seam["events"]:
        if e["kind"] == "write":
            out.append({"t": "W", "ordinal": w, "offset": e["offset"], "bytes": e["bytes"], "failed": not e["ok"],
                        "fault": e.get("fault")})
            w += 1
        elif e["kind"] == "flush":
            out.append({"t": "F", "ordinal": f, "os_call": e["os_call"], "failed": not e["success"],
                        "os_error": e["os_error"], "fault": e.get("fault")})
            f += 1
    return out


class Out:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.files: dict[str, str] = {}

    def put(self, rel: str, data: bytes) -> str:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_bytes(data)
        self.files[rel] = sha(p.read_bytes())
        return rel

    def put_json(self, rel: str, obj) -> str:
        return self.put(rel, (json.dumps(obj, indent=1, sort_keys=True) + "\n").encode())


def run_fault(o: Out, w, tmp: Path, kind: str, ordinal, pristine: bytes, wav_sha: str):
    name = f"{kind}-{ordinal}" if ordinal is not None else kind
    fault = {"write": f"write-error:{ordinal}", "barrier": f"flush-error:{ordinal}"}.get(kind)
    if kind == "native-flush-error":
        fault = "native-flush-error"
    img = tmp / "fault-input.img"
    img.write_bytes(pristine)
    before = sha(img.read_bytes())
    work = tmp / "load.img"
    shutil.copyfile(img, work)
    tr = tmp / "fault-trace.json"
    env = {"TAPECTL_TEST_TRACE": str(tr), "TAPECTL_TEST_PAYLOADS": "1"}
    if fault:
        env["TAPECTL_TEST_FAULT"] = fault
    t0 = time.time()
    r = rl.tapectl(["load", str(work), str(rl.SOURCE)], env)
    seam_raw = tr.read_bytes()
    seam = json.loads(seam_raw)
    ev = events(seam)
    after = work.read_bytes()
    rel = f"faults/{name}"
    o.put(f"{rel}/seam-trace.json", seam_raw)
    o.put(f"{rel}/image-after.img.gz", gzip.compress(after, 6))
    post = rl.remount(w, tmp, ("load", "voice.wav"), after)
    want = {"write": "W", "barrier": "F"}.get(kind)
    hit = [e for e in ev if want and e["t"] == want and e["ordinal"] == ordinal]
    fired = len(hit) == 1 and hit[0]["failed"] and hit[0]["fault"] in ("write-error", "flush-error")
    rec = {"kind": "actual-fault-execution" if want else "route-control",
           "requested": {"kind": kind, "ordinal": ordinal, "seam_fault": fault},
           "fault_fired": fired if want else None,
           "exit": r.returncode, "stdout": r.stdout, "stderr": r.stderr, "seconds": round(time.time() - t0, 3),
           "load_events": ev, "op_calls": sum(e["t"] == "W" for e in ev), "op_barriers": sum(e["t"] == "F" for e in ev),
           "failed_events": [e for e in ev if e["failed"]],
           "working_effects_known": True,
           "working_effects": ("the failed write call was issued on an invalidated handle and the OS returned "
                               "an error for it: none of its bytes reached the image; every other call is as "
                               "traced (payloads retained)") if kind == "write" else
                              ("a failed barrier moves no bytes; every write is as traced (payloads retained)"),
           "actual_input_sha256": before, "pristine_input_sha256": PLAN["baseline"]["initial_sha256"],
           "image_after_sha256": sha(after), "source_wav_sha256": wav_sha,
           "expected_source_wav_sha256": wav_sha, "seam_trace_sha256": sha(seam_raw),
           "post_failure_remount": post, "remaining_coordinate_status": "executed" if want else None,
           "binary_sha256": sd.sha_file(rl.TAPECTL)}
    o.put_json(f"{rel}/record.json", rec)
    return name, rec


def retained_rows(retained: Path):
    remounts, runs = {}, []
    for f in sorted(retained.glob("load/*/remounts.jsonl")):
        for line in f.read_text().splitlines():
            d = json.loads(line)
            remounts.setdefault(d["projection_sha256"], (f.parent, line))
    for f in sorted(retained.glob("load/*/runs.jsonl")):
        for line in f.read_text().splitlines():
            d = json.loads(line)
            if d.get("format") == "WP10-SUBSET-RUN-ROW-1":
                runs.append((f.parent, d))
    return remounts, runs


def select(remounts: dict, empty: str, new: str):
    def state(d):
        names = {empty: "empty", new: "new"}
        return "/".join(names.get(d[c]["wav_sha256"], "other") for c in ("dump_A", "dump_B"))
    first, repair = {}, []
    for h in sorted(remounts):
        d = json.loads(remounts[h][1])
        first.setdefault(state(d), h)
        if any(e.get("needs_repair") for c in ("verify", "dump_A", "dump_B") for e in d[c]["engine"]
               if e["kind"] == "engine_info"):
            repair.append(h)
    picks = {h: ["first " + s] for s, h in first.items()}
    for h in repair:
        picks.setdefault(h, []).append("needs_repair")
    return picks


def rebuild(part: Path, row: dict, want: str) -> bytes:
    initial = gzip.decompress((part / "initial" / f"{row['initial_sha256']}.img.gz").read_bytes())
    t = row["trace"]
    if t["stored"] == "whole":
        trace = [json.loads(x) for x in gzip.decompress((part / "traces" / f"{t['trace_sha256']}.jsonl.gz")
                                                        .read_bytes()).decode().splitlines() if x.strip()]
    else:
        ref = [json.loads(x) for x in gzip.decompress((part / "traces" / f"{t['reference_trace_sha256']}.jsonl.gz")
                                                      .read_bytes()).decode().splitlines() if x.strip()]
        cut = t["cut_record"].get("call")
        trace = [dict(r, ack=False) if r["t"] == "W" and r["call"] == cut else r for r in ref[:t["prefix_records"]]]
        trace.append(t["cut_record"])
    raw = "".join(json.dumps(r, sort_keys=True) + "\n" for r in trace).encode()
    if sha(raw) != t["trace_sha256"]:
        raise RuntimeError("rebuilt trace does not match its retained hash")
    dev = sd.replay(initial, trace)
    _, plan = sd.plans(dev.events)
    nblocks = len(initial) // sd.BLOCK
    durable = sd.materialize(dev, [], nblocks)
    touched = sorted({e.lba for e in dev.events if e.lba < nblocks})
    for q in row["projections"]:
        if q["image_sha256"] != want:
            continue
        for p in plan:
            if ("landing_order" in q and p["landing_order"] == q["landing_order"]) or \
               ("landing_order_sha256" in q and sha(sd._canon(p["landing_order"])) == q["landing_order_sha256"]):
                img = sd.projection(dev, p["landing_order"], durable, touched)
                if sha(img) == want:
                    return img
    raise RuntimeError(f"projection {want[:12]} not rebuilt from its run row")


def command_row(o: Out, w, tmp: Path, h: str, why, part: Path, remount_line: str, runs):
    has = [(p, d) for p, d in runs if any(q.get("image_sha256") == h for q in d.get("projections", []))]
    part, row = next(((p, d) for p, d in has if p == part), has[0])
    img = rebuild(part, row, h)
    rel = f"commands/{h}"
    o.put(f"{rel}/projection.img", img)
    o.put(f"{rel}/original-remount.json", remount_line.encode() + b"\n")
    cmds, raw_inputs = {}, {}
    for cmd in ("verify", "dump_A", "dump_B"):
        p = tmp / f"cmd-{cmd}.img"
        p.write_bytes(img)
        tr = tmp / f"cmd-{cmd}-trace.json"
        if tr.exists():
            tr.unlink()
        if cmd == "verify":
            r = rl.tapectl(["verify", str(p)], {"TAPECTL_TEST_TRACE": str(tr)})
        else:
            wav = tmp / f"cmd-{cmd}.wav"
            if wav.exists():
                wav.unlink()
            r = rl.tapectl(["dump", str(p), "--side", cmd[-1], "-o", str(wav)], {"TAPECTL_TEST_TRACE": str(tr)})
        seam_raw = tr.read_bytes()
        seam = json.loads(seam_raw)
        after = p.read_bytes()
        o.put(f"{rel}/{cmd}-seam.json", seam_raw)
        after_rel = f"{rel}/projection.img" if sha(after) == h else o.put(f"{rel}/{cmd}-after.img", after)
        binds = [e for e in seam["events"] if e["kind"] == "engine_bind"]
        mounts = [e for e in seam["events"] if e["kind"] == "engine_mount"]
        c = {"exit": r.returncode, "stdout": r.stdout, "stderr": r.stderr, "fresh_process": True,
             "own_pristine_copy": True, "cold_mount": bool(mounts) and all(m.get("cold") for m in mounts),
             "full_seam_retained": True, "seam_trace": f"{rel}/{cmd}-seam.json",
             "write_callback_null": bool(binds) and all(b["write_is_null"] for b in binds),
             "write_events": [e for e in seam["events"] if e["kind"] == "write"],
             "engine": [e for e in seam["events"] if e["kind"] in ("engine_bind", "engine_mount", "engine_info")],
             "input_before_sha256": h, "input_after_sha256": sha(after)}
        if cmd != "verify":
            c["wav_sha256"] = sha(wav.read_bytes()) if wav.exists() else None
            if wav.exists():
                o.put(f"{rel}/{cmd}.wav", wav.read_bytes())
        cmds[cmd] = c
        raw_inputs[cmd] = {"before": f"{rel}/projection.img", "after": after_rel}
    rec = {"kind": "complete-history-projection", "projection_sha256": h, "selected_as": why,
           "run_row": {"part": part.name, "coordinate": row["coordinate"], "label": row["label"],
                       "trace": row["trace"], "initial_sha256": row["initial_sha256"]},
           "commands": cmds, "binary_sha256": sd.sha_file(rl.TAPECTL)}
    o.put_json(f"{rel}/record.json", rec)
    return {"name": f"commands-{h[:12]}", "record": f"{rel}/record.json",
            "original_observation": f"{rel}/original-remount.json", "raw_inputs": raw_inputs}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--retained", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    o = Out(a.out)
    tmp = a.out.parent / (a.out.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    t0 = time.time()
    w = rl.make_worker(tmp)
    pristine = w.base.read_bytes()
    if sha(pristine) != PLAN["baseline"]["initial_sha256"]:
        raise SystemExit("provisioned image is not the plan's baseline " + sha(pristine))
    wav_sha = sd.sha_file(rl.SOURCE)
    fault_rows, summary = [], []
    for kind, ordinal in CONTROLS + PILOT:
        name, rec = run_fault(o, w, tmp, kind, ordinal, pristine, wav_sha)
        summary.append({"name": name, "exit": rec["exit"], "fault_fired": rec["fault_fired"],
                        "op_calls": rec["op_calls"], "op_barriers": rec["op_barriers"],
                        "failed": [(e["t"], e["ordinal"]) for e in rec["failed_events"]]})
        print(json.dumps(summary[-1]), flush=True)
        if rec["kind"] == "actual-fault-execution":
            fault_rows.append({"name": name, "record": f"faults/{name}/record.json"})
    base = json.loads((a.out / "faults/none/record.json").read_text())
    if (base["op_calls"], base["op_barriers"]) != (PLAN["baseline"]["op_calls"], PLAN["baseline"]["op_barriers"]):
        raise SystemExit("no-fault route is not the plan's 353-call/52-barrier baseline")
    remounts, runs = retained_rows(a.retained)
    complete = rl.remount(w, tmp, ("load", "voice.wav"), gzip.decompress(
        (a.out / "faults/none/image-after.img.gz").read_bytes()))
    initial = rl.remount(w, tmp, ("load", "voice.wav"), pristine)
    empty, new = initial["dump_A"]["wav_sha256"], complete["dump_A"]["wav_sha256"]
    picks = select(remounts, empty, new)
    command_rows = []
    for h, why in picks.items():
        part, line = remounts[h]
        command_rows.append(command_row(o, w, tmp, h, why, part, line, runs))
        print(json.dumps({"projection": h, "selected_as": why}), flush=True)
    status = {"write": {}, "barrier": {}}
    for x in range(PLAN["old_missing"]["write_ordinals"][0], PLAN["old_missing"]["write_ordinals"][1] + 1):
        status["write"][x] = "executed" if ("write", x) in PILOT else "unexecuted"
    for x in range(PLAN["old_missing"]["barrier_ordinals"][0], PLAN["old_missing"]["barrier_ordinals"][1] + 1):
        status["barrier"][x] = "executed" if ("barrier", x) in PILOT else "unexecuted"
    o.put_json("COORDINATES.json", {"note": "404 previously missing coordinates; 'unexecuted' entries are now "
                                    "reachable through write-error:N / flush-error:N but were not run (pilot only)",
                                    "status": status})
    ru_c, ru_s = resource.getrusage(resource.RUSAGE_CHILDREN), resource.getrusage(resource.RUSAGE_SELF)
    cost = {"cpu_seconds_children": ru_c.ru_utime + ru_c.ru_stime, "cpu_seconds_self": ru_s.ru_utime + ru_s.ru_stime,
            "wall_seconds": round(time.time() - t0, 1),
            "raw_bytes": sum((a.out / f).stat().st_size for f in o.files)}
    o.put_json("COST.json", cost)
    bundle = {"files": o.files, "duplicate_rows": [], "fault_rows": fault_rows, "command_rows": command_rows,
              "route_controls": ["faults/none/record.json", "faults/native-flush-error/record.json"],
              "fault_summary": summary}
    (a.out / "BUNDLE.json").write_text(json.dumps(bundle, indent=1, sort_keys=True) + "\n")
    shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(cost))


if __name__ == "__main__":
    main()
