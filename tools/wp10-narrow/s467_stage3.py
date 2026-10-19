#!/usr/bin/env python3
"""#467 Stage3 (tests/wp10_subset_extension_r1/PLAN.json), lanes in the plan's order.

    python3 -B tools/wp10-narrow/s467_stage3.py --retained-loads DIR --out DIR

DIR holds the four retained load shards unzipped side by side (load/part-00N-MM/...).

Lane 1, global-empty-command: the plan's projection (the global minimum empty/empty
projection over all four shards; checked here) is rebuilt from its retained initial
image, trace and landing order and remounted by verify / dump A / dump B, each a fresh
process on its own copy with its full seam (s467_load.command_row, unchanged).

Lane 2, next32-load-faults: the plan's 32 fixed coordinates, each an actual selected
failure through the tapectl-test seam (write-error:N / flush-error:N), with the no-fault
positive repeated as the route control (s467_load.run_fault, unchanged).

Lane 3, atomic-residue: for each of the plan's 12 raw shapes x {dup, format}, the
crafted initial image is built by the pinned independent builders (wp10_residue_d10/
plan.py: base() over EXHAUSTION_SHAPES / RESIDUE_SHAPES, blank() for the two blank
variants), expanded to the full device, and given as the run's base to the existing
format/dup worker through the existing binding (run_dup, subset_driver.Campaign): one
complete positive neighbour, then the four fixed cuts. The binding key's shape is a
placeholder that the base image replaces; each row's label names the crafted shape.

Lane 4, long-copy-repeated-LBA: the existing respool_full binding (run_respool) on its
three fixtures at the six fixed unit cuts, with the binding's own projections.

For every lane-3/4 epoch over 8 events the plan's nine targeted landing orders
(orders.targeted) are projected and remounted too (EXTRA-ORDERS.jsonl). Evidence is
the bindings' own WP10-SUBSET runs/remounts/traces format.
"""
from __future__ import annotations

import argparse
import gzip
import json
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "wp10-narrow"))
import s467_load as L  # noqa: E402
sys.path.insert(0, str(ROOT / "tests" / "wp10_residue_d10"))
sys.path.insert(0, str(ROOT / "tests" / "wp10_subset_extension_r1"))
# run_dup and run_respool each import a different `fixture` module, so each lane imports
# its own binding, and lane 4 runs in a separate process of this script (--lane4).
import plan as RP  # noqa: E402  (independent residue builders, pinned)
from orders import targeted  # noqa: E402

SD = L.sd
PLAN = json.loads((ROOT / "tests/wp10_subset_extension_r1/PLAN.json").read_text())


def full_image(blocks: dict) -> bytes:
    img = bytearray((RP.M.MIRROR + 1) * RP.M.BLOCK)
    for name, lba in RP.M.TRACKED.items():
        img[lba * RP.M.BLOCK:(lba + 1) * RP.M.BLOCK] = blocks[name]
    return bytes(img)


def crafted(shape: str) -> dict:
    if shape in RP.BLANK_VARIANTS:
        return RP.blank(shape)
    if shape in RP.EXHAUSTION_SHAPES:
        return RP.base(*RP.EXHAUSTION_SHAPES[shape])
    return RP.base(*RP.RESIDUE_SHAPES[shape])


def extra_orders(c, key, dev, label, sink):
    """The plan's nine targeted orders for an epoch over the small-epoch limit."""
    if len(dev.events) <= PLAN["persistence"]["small_epoch_limit"]:
        return 0
    evs = [{"id": e.id, "lba": e.lba} for e in dev.events]
    n = 0
    for t in targeted(evs):
        img = SD.projection(dev, t["landing_order"], c._durable, c._touched)
        h = c.remount(key, img)
        sink.write(json.dumps({"label": label, "scenario": list(key), "name": t["name"], "mask": t["mask"],
                               "landing_order": t["landing_order"], "image_sha256": h}) + "\n")
        n += 1
    return n



def run_with_extras(c, key, label, sink, **kw):
    res, dev, full = c.run(key, label=label, **kw)
    c.runs.flush()
    row = json.loads((c.ev / "runs.jsonl").read_text().splitlines()[-1])
    initial = gzip.decompress((c.ev / "initial" / f"{row['initial_sha256']}.img.gz").read_bytes())
    nb = len(initial) // SD.BLOCK
    c._durable = SD.materialize(dev, [], nb)
    c._touched = sorted({e.lba for e in dev.events if e.lba < nb})
    x = extra_orders(c, key, dev, label, sink)
    return {"label": label, "result": res.get("operation_result"), "cut_fired": res.get("cut_fired"),
            "epoch_events": len(dev.events), "projections": len(full), "extra_orders": x,
            "repeated_lba_events": len(dev.events) - len({e.lba for e in dev.events})}


def lane4_main(out: Path):
    import run_respool as RR
    tmp = out.parent / (out.name + ".tmp4")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)

    def campaign(binding, sub):
        ev = out / sub
        ev.mkdir(parents=True, exist_ok=True)
        wt = tmp / sub
        wt.mkdir(parents=True, exist_ok=True)
        return SD.Campaign(binding, ev, binding.make_worker(wt), wt), ev

    c4, ev4 = campaign(RR, "lane4")
    sink4 = open(ev4 / "EXTRA-ORDERS.jsonl", "w")
    rows4 = []
    for scen in PLAN["long_copy"]["scenarios"]:
        key = tuple(scen)
        for coord in PLAN["long_copy"]["coordinates"]:
            r = run_with_extras(c4, key, f"{'/'.join(scen)}/{json.dumps(coord, sort_keys=True)}", sink4,
                                cut_unit=str(coord["cut_op_unit"]))
            c4.runs.flush()
            units = json.loads((ev4 / "runs.jsonl").read_text().splitlines()[-1])["worker"].get("op_units")
            # A coordinate absent from the actual trace is UNEXECUTED with that trace (PLAN README).
            r["status"] = "executed" if r["cut_fired"] else f"UNEXECUTED: the operation's actual trace has {units} units"
            rows4.append(dict(r, scenario=scen, coordinate=coord))
            print(json.dumps({"lane": 4, **{k: rows4[-1][k] for k in ("label", "status", "result", "epoch_events",
                                                                       "projections", "extra_orders",
                                                                       "repeated_lba_events")}}), flush=True)
    sink4.close()
    c4.close()
    (ev4 / "LANE4.json").write_text(json.dumps({
        "status": "executed where the coordinate exists", "rows": rows4,
        "repeated_lba_events_total": sum(r["repeated_lba_events"] for r in rows4),
        "note": "no epoch here has a repeated LBA; no repeated-LBA coverage is inferred from these traces"},
        indent=1) + "\n")
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--lane4":
        return lane4_main(Path(sys.argv[2]))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--retained-loads", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    o = L.Out(a.out)
    tmp = a.out.parent / (a.out.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    t0 = time.time()
    w = L.rl.make_worker(tmp)
    pristine = w.base.read_bytes()
    if L.sha(pristine) != L.PLAN["baseline"]["initial_sha256"]:
        raise SystemExit("provisioned image is not the baseline")
    wav_sha = L.sd.sha_file(L.rl.SOURCE)
    lanes = {}

    # Lane 1
    remounts, runs = L.retained_rows(a.retained_loads)
    empty = L.rl.remount(w, tmp, ("load", "voice.wav"), pristine)["dump_A"]["wav_sha256"]
    _, base = L.run_fault(o, w, tmp, "none", None, pristine, wav_sha)
    new = base["post_failure_remount"]["dump_A"]["wav_sha256"]
    picks = L.select(remounts, empty, new)
    first_empty = next(h for h, why in picks.items() if "first empty/empty" in why)
    want = PLAN["global_empty_command"]
    if first_empty != want:
        raise SystemExit(f"global first empty/empty is {first_empty}, the plan names {want}")
    part, line = remounts[want] if want in remounts else (None, None)
    if line is None:
        has = [(p, d) for p, d in runs if any(q.get("image_sha256") == want for q in d.get("projections", []))]
        part = has[0][0]
        line = json.dumps({"projection_sha256": want, "note": "no retained remount row in any shard"})
    row = L.command_row(o, w, tmp, want, ["global first empty/empty (PLAN global_empty_command)"], part, line, runs)
    lanes["global-empty-command"] = {"status": "executed", "projection": want, "shard_part": part.name}
    print(json.dumps({"lane": 1, "projection": want, "part": part.name}), flush=True)

    # Lane 2
    fault_rows, summary = [], []
    for f in PLAN["load_faults"]:
        name, rec = L.run_fault(o, w, tmp, f["kind"], f["ordinal"], pristine, wav_sha)
        fault_rows.append({"name": name, "record": f"faults/{name}/record.json"})
        summary.append({"name": name, "exit": rec["exit"], "fault_fired": rec["fault_fired"],
                        "failed": [(e["t"], e["ordinal"]) for e in rec["failed_events"]]})
        print(json.dumps(summary[-1]), flush=True)
    lanes["next32-load-faults"] = {"status": "executed", "count": len(fault_rows),
                                   "fired": sum(1 for s in summary if s["fault_fired"])}

    # Lane 3
    def campaign(binding, sub):
        ev = a.out / sub
        ev.mkdir(parents=True, exist_ok=True)
        wt = tmp / sub
        wt.mkdir(parents=True, exist_ok=True)
        return SD.Campaign(binding, ev, binding.make_worker(wt), wt), ev

    import run_dup as RD
    c3, ev3 = campaign(RD, "lane3")
    sink3 = open(ev3 / "EXTRA-ORDERS.jsonl", "w")
    rows3 = []
    for op in PLAN["atomic_residue"]["operations"]:
        for shape in PLAN["atomic_residue"]["shapes"]:
            bp = tmp / f"base-{shape}.img"
            bp.write_bytes(full_image(crafted(shape)))
            o.put(f"lane3/bases/{shape}.img.sha256", (L.sha(bp.read_bytes()) + "\n").encode())
            key = (op, "healthy_pair")
            rows3.append(dict(run_with_extras(c3, key, f"{op}/{shape}/complete", sink3, base=str(bp)), op=op, shape=shape))
            for coord in PLAN["atomic_residue"]["coordinates"]:
                kw = {"cut_unit": str(coord["cut_op_unit"])} if "cut_op_unit" in coord else \
                     {"cut_flush": str(coord["cut_op_barrier_entry"])}
                rows3.append(dict(run_with_extras(c3, key, f"{op}/{shape}/{json.dumps(coord, sort_keys=True)}", sink3,
                                                  base=str(bp), **kw), op=op, shape=shape, coordinate=coord))
            print(json.dumps({"lane": 3, "op": op, "shape": shape, "rows": [(r["result"], r["cut_fired"], r["epoch_events"])
                                                                         for r in rows3[-5:]]}), flush=True)
    sink3.close()
    c3.close()
    lanes["atomic-residue"] = {"status": "executed", "rows": rows3,
                               "max_epoch_events": max(r["epoch_events"] for r in rows3),
                               "note": "binding key shape 'healthy_pair' is a placeholder replaced by the crafted base"}

    # Lane 4 (own process)
    r = subprocess.run([sys.executable, "-B", __file__, "--lane4", str(a.out)], capture_output=True, text=True)
    print(r.stdout, end="", flush=True)
    if r.returncode != 0:
        raise SystemExit("lane 4 failed:\n" + r.stderr)
    lanes["long-copy-repeated-LBA"] = json.loads((a.out / "lane4" / "LANE4.json").read_text())
    for sub in ("lane3", "lane4"):
        for f in sorted((a.out / sub).rglob("*")):
            if f.is_file():
                o.files[str(f.relative_to(a.out))] = L.sha(f.read_bytes())
    o.put_json("LANES.json", lanes)
    ru_c, ru_s = resource.getrusage(resource.RUSAGE_CHILDREN), resource.getrusage(resource.RUSAGE_SELF)
    cost = {"cpu_seconds_children": ru_c.ru_utime + ru_c.ru_stime, "cpu_seconds_self": ru_s.ru_utime + ru_s.ru_stime,
            "wall_seconds": round(time.time() - t0, 1),
            "raw_bytes": sum((a.out / f).stat().st_size for f in o.files)}
    o.put_json("COST.json", cost)
    bundle = {"files": o.files, "duplicate_rows": [], "fault_rows": fault_rows, "command_rows": [row],
              "route_controls": ["faults/none/record.json"], "fault_summary": summary, "lanes": "LANES.json",
              "subset_evidence": {"atomic-residue": "lane3", "long-copy-repeated-LBA": "lane4"}}
    (a.out / "BUNDLE.json").write_text(json.dumps(bundle, indent=1, sort_keys=True) + "\n")
    shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(cost))


if __name__ == "__main__":
    main()
