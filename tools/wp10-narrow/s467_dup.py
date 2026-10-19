#!/usr/bin/env python3
"""#467 Tier 1: duplication source/label/PCM binding for the two selected restored
destinations of Verification #210 (tests/wp10_narrow_supplement_r1/ADAPTER.md §1).
Software transports raw facts; Verification's replay.py derives labels and PCM
equality itself. No engine change.

    python3 -B tools/wp10-narrow/s467_dup.py --retained-small DIR --out DIR

Source: the existing adapter's source fixture (format_dup_identity_adapter/adapter.py
write_source, not a new golden). For every shape the selected contexts use, the worker's
`Q` command runs one complete, unfaulted tape_dup with the source context named
"source": every source and destination callback is logged, the binding's write callback
is recorded as the worker actually passed it to tape_init, and the worker's own source
bytes are saved before and after. A control build (make mutant:
-DS467_SOURCE_WRITE_MUTANT) gives the source binding a write callback; its row must
show source_write_callback_null false.

Destinations: each selected projection is rebuilt from the retained small packet's
initial image, trace and landing order with the binding's own replay/projection code,
and checked against its hash before use.

Renders: tapectl-test dump --side A and B (fresh process, own copy, full seam trace) of
the source and of each destination; the PCM files are the WAV data chunks.
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "wp10-narrow"))
sys.path.insert(0, str(ROOT / "tests" / "format_dup_identity_adapter"))
import s467_load as L  # noqa: E402  (Out, rebuild, run rows; also loads run_load / subset_driver)
import adapter as fd  # noqa: E402

SEL = json.loads((ROOT / "tests/wp10_narrow_supplement_r1/SELECTED-DESTINATIONS.json").read_text())
MUTANT = ROOT / "tests/format_dup_identity_adapter/build/r29_format_dup_worker_s467_mutant"
DUP_UUID = bytes(range(0xb0, 0xc0))      # the worker's dup_uuid


def pcm_of(wav: bytes) -> bytes:
    if wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        raise RuntimeError("not a WAV")
    i = 12
    while i + 8 <= len(wav):
        cid, n = wav[i:i + 4], struct.unpack_from("<I", wav, i + 4)[0]
        if cid == b"data":
            return wav[i + 8:i + 8 + n]
        i += 8 + n + (n & 1)
    raise RuntimeError("no data chunk")


def worker(binary: Path, tmp: Path):
    src, big = tmp / "source.bin", tmp / "source_big.bin"
    fd.write_source(src)
    fd.write_source_big(big)
    shapes = []
    for name in fd.raw_shapes():
        p = tmp / f"{name}.bin"
        fd.write_shape(p, name)
        shapes.append(str(p))
    return subprocess.Popen([str(binary), str(src), str(big)] + shapes, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True)


def ask(w, *fields) -> dict:
    w.stdin.write("\t".join(fields) + "\n")
    w.stdin.flush()
    line = w.stdout.readline()
    if not line:
        raise RuntimeError("worker exited")
    return json.loads(line)


def dump(o: L.Out, tmp: Path, image: bytes, rel: str, side: str) -> dict:
    p, wav, tr = tmp / f"dump-{side}.img", tmp / f"dump-{side}.wav", tmp / f"dump-{side}.json"
    for x in (wav, tr):
        if x.exists():
            x.unlink()
    p.write_bytes(image)
    r = L.rl.tapectl(["dump", str(p), "--side", side, "-o", str(wav)], {"TAPECTL_TEST_TRACE": str(tr)})
    seam_raw = tr.read_bytes()
    seam = json.loads(seam_raw)
    o.put(f"{rel}/dump-{side}-seam.json", seam_raw)
    mounts = [e for e in seam["events"] if e["kind"] == "engine_mount"]
    out = {"exit": r.returncode, "stderr": r.stderr, "mount": mounts[0]["result"] if mounts else None,
           "seam": f"{rel}/dump-{side}-seam.json", "input_unchanged": L.sha(p.read_bytes()) == L.sha(image)}
    if r.returncode == 0 and wav.exists():
        pcm = pcm_of(wav.read_bytes())
        out.update(frames=len(pcm) // 4, pcm=o.put(f"{rel}/{side}.pcm", pcm), wav=o.put(f"{rel}/{side}.wav", wav.read_bytes()))
    return out


def source_run(o: L.Out, w, tmp: Path, shape: str, rel: str) -> dict:
    d = o.root / rel
    d.mkdir(parents=True, exist_ok=True)
    res = ask(w, "Q", shape, str(d))
    ev = [json.loads(x) for x in (d / "events.jsonl").read_text().splitlines() if x.strip()]
    for n in ("source-before.img", "source-after.img", "destination-before.img", "destination-after.img",
              "events.jsonl"):
        o.files[f"{rel}/{n}"] = L.sha((d / n).read_bytes())
    src = [e for e in ev if e["device"] == "source"]
    return {"worker": res, "shape": shape, "source_before": f"{rel}/source-before.img",
            "source_after": f"{rel}/source-after.img", "events": f"{rel}/events.jsonl",
            "source_write_callback_null": res["source_write_callback_null"],
            "source_write_events": [e for e in src if e["op"] != "r"],
            "source_trace_complete": res["events_logged"] < res["events_capacity"],
            "source_positive_read_seen": any(e["op"] == "r" and e["rc"] == 0 for e in src)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--retained-small", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    o = L.Out(a.out)
    tmp = a.out.parent / (a.out.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    w = worker(fd.WORKER, tmp)
    shapes = sorted({c["scenario"][1] for x in SEL["destinations"] for c in x["contexts"]})
    sources = {s: source_run(o, w, tmp, s, f"source/{s}") for s in shapes}
    w.stdin.write("D\n"); w.stdin.flush(); w.wait()
    m = worker(MUTANT, tmp)
    control = source_run(o, m, tmp, shapes[0], f"source-mutant/{shapes[0]}")
    m.stdin.write("D\n"); m.stdin.flush(); m.wait()
    for s, r in sources.items():
        print(json.dumps({"source_run": s, **{k: r[k] for k in ("source_write_callback_null", "source_trace_complete",
                                                                  "source_positive_read_seen")},
                          "source_writes": len(r["source_write_events"]), "result": r["worker"]["operation_result"]}),
              flush=True)
    print(json.dumps({"mutant_control": shapes[0], "source_write_callback_null": control["source_write_callback_null"]}),
          flush=True)
    any_src = sources[shapes[0]]
    src_img = (o.root / any_src["source_before"]).read_bytes()
    src_dump = {side: dump(o, tmp, src_img, "source/render", side) for side in "AB"}
    remounts, runs = {}, []
    for f in sorted(a.retained_small.glob("dup/*/runs.jsonl")):
        for line in f.read_text().splitlines():
            d = json.loads(line)
            if d.get("format") == "WP10-SUBSET-RUN-ROW-1":
                runs.append((f.parent, d))
    rows = []
    for x in SEL["destinations"]:
        h = x["projection_sha256"]
        has = [(p, d) for p, d in runs if any(q.get("image_sha256") == h for q in d.get("projections", []))]
        part, row = has[0]
        img = L.rebuild(part, row, h)
        rel = f"destinations/{h}"
        o.put(f"{rel}/restored.img", img)
        dd = {side: dump(o, tmp, img, rel, side) for side in "AB"}
        ctx_shape = row["scenario"][1]
        s = sources[ctx_shape]
        rec = {"selected_projection_sha256": h, "rebuilt_from": {"part": part.name, "coordinate": row["coordinate"],
                                                                 "label": row["label"], "scenario": row["scenario"]},
               "source_fixture": "format_dup_identity_adapter/adapter.py write_source (existing Product setup)",
               "source_run_shape": ctx_shape, "source_worker_result": s["worker"],
               "source_write_callback_null": s["source_write_callback_null"],
               "source_write_events": s["source_write_events"], "source_trace_complete": s["source_trace_complete"],
               "source_positive_read_seen": s["source_positive_read_seen"], "source_events": s["events"],
               "source_ctx": "source", "destination_ctx": "destination",
               "source_A_frames": src_dump["A"].get("frames"), "source_B_frames": src_dump["B"].get("frames"),
               "source_A_mount": src_dump["A"]["mount"], "source_B_mount": src_dump["B"]["mount"],
               "destination_A_mount": dd["A"]["mount"], "destination_B_mount": dd["B"]["mount"],
               "destination_identity": "fresh" if DUP_UUID in img else "not-fresh",
               "destination_identity_method": "the worker's dup_uuid b0..bf is present in the restored image",
               "renders": {"source": src_dump, "destination": dd},
               "worker_sha256": L.sd.sha_file(fd.WORKER), "mutant_sha256": L.sd.sha_file(MUTANT),
               "tapectl_test_sha256": L.sd.sha_file(L.rl.TAPECTL)}
        o.put_json(f"{rel}/record.json", rec)
        rows.append({"name": f"dup-{h[:12]}", "record": f"{rel}/record.json", "source_before": s["source_before"],
                     "source_after": s["source_after"], "destination": f"{rel}/restored.img",
                     "source_A_pcm": src_dump["A"].get("pcm"), "source_B_pcm": src_dump["B"].get("pcm"),
                     "dest_A_pcm": dd["A"].get("pcm"), "dest_B_pcm": dd["B"].get("pcm")})
        print(json.dumps({"destination": h[:12], "A": dd["A"]["mount"], "B": dd["B"]["mount"],
                          "frames": [dd["A"].get("frames"), dd["B"].get("frames")],
                          "identity": rec["destination_identity"]}), flush=True)
    o.put_json("source-mutant-control.json", control)
    bundle = {"files": o.files, "duplicate_rows": rows, "fault_rows": [], "command_rows": [],
              "source_runs": {s: r["worker"] for s, r in sources.items()},
              "source_mutant_control": "source-mutant-control.json"}
    (a.out / "BUNDLE.json").write_text(json.dumps(bundle, indent=1, sort_keys=True) + "\n")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
