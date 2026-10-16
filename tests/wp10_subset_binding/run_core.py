#!/usr/bin/env python3
"""Any-subset campaign through the existing WP-10 core worker (record/commit, reset-b,
stage-clear closures). Product #440; see subset_driver.py for what is and is not done here.

    python3 tests/wp10_subset_binding/run_core.py --evidence DIR [--only FAMILY] [--second-cut N]

For each accepted crash_core_draft8 scenario (family, variant, seed) it runs, from the
scenario's fixture:
  * the complete operation (successful-operation control; crash at its end);
  * a cut at every operation write-unit boundary (0 .. units, including inside a
    multi-block call) and at the entry of every operation barrier;
  * an error at every operation write call and every operation barrier (crash at end).
Each run's actual history is replayed into model.py; every planned projection is
materialized and every distinct image is remounted. With --second-cut N, the first N
distinct first-cut images per scenario (in plan order) are each used as the base of a fresh
run of the same operation after actual recovery, cut at every unit boundary again.

Evidence: runs.jsonl (one row per run: coordinate, trace/initial hashes, epoch, every
mask/order/image hash), remounts.jsonl (one raw R observation per distinct image),
traces/ (every actual trace, gzip), initial/ (every distinct initial image, gzip), and
summary.json. No outcome verdict is produced.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tests" / "crash_core_draft8"))
import subset_driver as sd  # noqa: E402
import runner as core_runner  # noqa: E402  (verifier package: its own fixture writer)
from planner import iter_cases  # noqa: E402

WORKER = ROOT / "tests" / "crash_core_adapter" / "build" / "wp10_core_worker"
FIXTURES = ["record_commit", "reset_healthy", "reset_degraded_equal", "stage_healthy",
            "stage_primary_only", "stage_mirror_only", "stage_primary_newer_mirror_stale",
            "stage_mirror_newer_primary_stale"]


def remount_side(family: str, variant: str) -> str:
    # the existing run_injected rule, unchanged
    return "A" if family == "reset_b" and variant == "degraded_equal" else "B"


class Campaign:
    def __init__(self, evidence: Path, worker: sd.Worker, tmp: Path):
        self.ev, self.w, self.tmp = evidence, worker, tmp
        (evidence / "traces").mkdir(parents=True, exist_ok=True)
        (evidence / "initial").mkdir(parents=True, exist_ok=True)
        self.runs = open(evidence / "runs.jsonl", "w")
        self.remounts = open(evidence / "remounts.jsonl", "w")
        self.seen = {}          # (image sha, side) -> remount row index
        self.n_runs = 0
        self.n_proj = 0

    def remount(self, image: bytes, side: str) -> str:
        h = sd.sha(image)
        key = (h, side)
        if key not in self.seen:
            p = self.tmp / "proj.img"
            p.write_bytes(image)
            obs = self.w.ask("R", str(p), side)
            if obs["image_snapshot"]["image_sha256"] != h:
                raise RuntimeError("worker remounted different bytes than the projection")
            obs["projection_sha256"] = h
            self.remounts.write(json.dumps(obs, sort_keys=True) + "\n")
            self.seen[key] = len(self.seen)
        return h

    def run(self, family, variant, seed, base="-", cut_unit="-", cut_flush="-", err_call="-",
            err_flush="-", label=None, extra=None):
        tr, init = self.tmp / "trace.jsonl", self.tmp / "initial.img"
        res = self.w.ask("S", family, variant, seed, base, str(cut_unit), str(cut_flush),
                         str(err_call), str(err_flush), str(tr), str(init))
        trace = sd.read_trace(tr)
        initial = init.read_bytes()
        tsha, isha = sd.sha_file(tr), sd.sha(initial)
        with gzip.open(self.ev / "traces" / f"{tsha}.jsonl.gz", "wb", compresslevel=6) as f:
            f.write(tr.read_bytes())
        ip = self.ev / "initial" / f"{isha}.img.gz"
        if not ip.exists():
            with gzip.open(ip, "wb", compresslevel=6) as f:
                f.write(initial)
        dev = sd.replay(initial, trace)
        kind, plan = sd.plans(dev.events)
        side = remount_side(family, variant)
        nblocks = len(initial) // sd.BLOCK
        proj = []
        for p in plan:
            img = sd.materialize(dev, p["landing_order"], nblocks)
            proj.append({**p, "image_sha256": self.remount(img, side)})
        lbas = [e.lba for e in dev.events]
        row = {"format": "WP10-SUBSET-CORE-RUN-1", "label": label, "family": family, "variant": variant,
               "seed": seed, "base": base if base == "-" else "projection:" + isha,
               "coordinate": {"cut_op_unit": cut_unit, "cut_op_barrier_entry": cut_flush,
                              "error_op_call": err_call, "error_op_barrier": err_flush},
               "worker": res, "trace_sha256": tsha, "initial_sha256": isha, "remount_side": side,
               "epoch": {"events": [{"id": e.id, "call": e.call, "lba": e.lba, "ack": e.acknowledged,
                                     "sha256": sd.sha(e.data)} for e in dev.events],
                         "length": len(dev.events), "repeated_lba_events": len(lbas) - len(set(lbas)),
                         "barrier_results": dev.flush_results, "durable_sha256": sd.sha(
                             b"".join(dev.durable.get(i, bytes(sd.BLOCK)) for i in range(nblocks)))},
               "plan": kind, "projections": proj,
               "distinct_images": len({q["image_sha256"] for q in proj})}
        if extra:
            row["second_cut_of"] = extra
        self.runs.write(json.dumps(row, sort_keys=True) + "\n")
        self.n_runs += 1
        self.n_proj += len(proj)
        return res, dev, proj

    def close(self):
        self.runs.close()
        self.remounts.close()


def scenarios(only=None):
    out = sorted({(c["family"], c["variant"], c.get("seed") or "-") for c in iter_cases()})
    return [s for s in out if only is None or s[0] == only]


def tasks(counts: dict, second: int) -> list[tuple]:
    """Every run coordinate, in a fixed order, so shards partition the campaign exactly."""
    out = []
    for key, (u, b, k) in counts.items():
        out.append((key, "complete", None))
        out += [(key, "cut_unit", i) for i in range(u + 1)]
        out += [(key, "cut_barrier_entry", j) for j in range(b)]
        out += [(key, "error_write", j) for j in range(k)]
        out += [(key, "error_barrier", j) for j in range(b)]
        out += [(key, "second", n) for n in range(second)]
    return out


def first_cut_base(c: "Campaign", key: tuple, u: int, n: int):
    """The n-th distinct durable image reached by first cuts at unit boundaries 0, 1, ...,
    in plan order (recomputed from actual runs, never cached from another process)."""
    seen = {}
    for i in range(u + 1):
        _, dev, proj = c.run(*key, cut_unit=i, label="first_cut_for_second")
        for q in proj:
            if q["image_sha256"] not in seen:
                seen[q["image_sha256"]] = (i, q, sd.materialize(dev, q["landing_order"], len(dev.durable)))
                if len(seen) > n:
                    return list(seen.values())[n]
    return None


def do_task(c: "Campaign", tmp: Path, task: tuple, counts: dict) -> None:
    key, kind, x = task
    u = counts[key][0]
    if kind == "complete":
        c.run(*key, label="complete")
    elif kind == "cut_unit":
        c.run(*key, cut_unit=x, label="cut_unit")
    elif kind == "cut_barrier_entry":
        c.run(*key, cut_flush=x, label="cut_barrier_entry")
    elif kind == "error_write":
        c.run(*key, err_call=x, label="error_write")
    elif kind == "error_barrier":
        c.run(*key, err_flush=x, label="error_barrier")
    elif kind == "second":
        # Second interruption after actual recovery: a fresh run of the same operation whose
        # base is a first-cut projection's durable bytes only, cut at every unit again.
        got = first_cut_base(c, key, u, x)
        if got is None:
            return
        i, q, img = got
        p = tmp / "second-base.img"
        p.write_bytes(img)
        tag = {"first_cut_op_unit": i, "first_mask": q["mask"], "first_landing_order": q["landing_order"],
               "first_image_sha256": q["image_sha256"], "second_base_index": x}
        r2, _, _ = c.run(*key, base="@" + str(p), label="second_complete", extra=tag)
        if r2["setup_ok"]:
            for j in range(r2["op_units"] + 1):
                c.run(*key, base="@" + str(p), cut_unit=j, label="second_cut", extra=tag)


def fixture_worker(tmp: Path) -> sd.Worker:
    paths = core_runner._write_fixtures(tmp / "fixtures")
    return sd.Worker([str(WORKER)] + [str(paths[n]) for n in FIXTURES])


def run_part(args) -> dict:
    evidence, part, counts, second = args
    tmp = Path(tempfile.mkdtemp())
    try:
        w = fixture_worker(tmp)
        c = Campaign(evidence, w, tmp)
        for t in part:
            do_task(c, tmp, t, counts)
        c.close()
        return {"worker_exit": w.close(), "runs": c.n_runs, "projections": c.n_proj,
                "distinct_remounted_images": len(c.seen), "tasks": len(part)}
    finally:
        shutil.rmtree(tmp)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--only")
    ap.add_argument("--second-cut", type=int, default=2)
    ap.add_argument("--shard", default="0/1", help="I/N: run tasks whose index %% N == I")
    ap.add_argument("--jobs", type=int, default=1, help="parallel worker processes in this shard")
    a = ap.parse_args(argv)
    si, sn = (int(v) for v in a.shard.split("/"))
    a.evidence.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    try:
        w = fixture_worker(tmp)
        counts = {}
        for key in scenarios(a.only):
            r = w.ask("S", *key, "-", "-", "-", "-", "-", str(tmp / "t.jsonl"), str(tmp / "i.img"))
            counts[key] = (r["op_units"], r["op_barriers"], r["op_calls"])
        w.close()
    finally:
        shutil.rmtree(tmp)
    allt = tasks(counts, a.second_cut)
    mine = [t for n, t in enumerate(allt) if n % sn == si]
    parts = [mine[j::a.jobs] for j in range(a.jobs)]
    import multiprocessing as mp
    jobs = [(a.evidence / f"part-{si:03d}-{j:02d}", parts[j], counts, a.second_cut) for j in range(a.jobs)]
    if a.jobs == 1:
        res = [run_part(jobs[0])]
    else:
        with mp.get_context("spawn").Pool(a.jobs) as pool:
            res = pool.map(run_part, jobs)
    summary = {"format": "WP10-SUBSET-CORE-SUMMARY-1", "shard": a.shard, "tasks_total": len(allt),
               "tasks_this_shard": len(mine), "parts": res,
               "scenarios": {"/".join(k): {"op_units": v[0], "op_barriers": v[1], "op_calls": v[2]}
                             for k, v in counts.items()},
               "second_cut_bases_per_scenario": a.second_cut,
               "model_sha256": sd.sha_file(sd.MODEL_PATH), "worker_sha256": sd.sha_file(WORKER),
               "seeds": list(sd.SEEDS)}
    (a.evidence / f"summary-{si:03d}.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"shard": a.shard, "tasks": len(mine), "runs": sum(r["runs"] for r in res),
                      "projections": sum(r["projections"] for r in res),
                      "worker_exits": [r["worker_exit"] for r in res]}))
    return 0 if all(r["worker_exit"] == 0 for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
