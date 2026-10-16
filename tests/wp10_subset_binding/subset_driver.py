"""Transport between a WP-10 worker's S/R commands and Verification's any-subset model.

Product #440 (tests/wp10_subset_r1/ADAPTER.md). Software transports actual callbacks and
raw observations only:

  * a worker S run returns the actual event history: every 512-byte write unit (absolute
    ID, call ID, LBA, bytes, acknowledgement) and every barrier result, from the initial
    durable image on, ending at a cut coordinate or at the operation's own end;
  * that history is replayed, call by call, into tests/wp10_subset_r1/model.py's Device,
    imported unchanged; the model's own exhaustive/sampled planners choose the masks and
    landing orders, and Device.crash_image materializes each durable projection;
  * each distinct projection is remounted by a worker R command from those bytes only
    (fresh engine instance and rings, no volatile state), and its raw output is kept.

Nothing here classifies an outcome. Verification compares the projections with model.py
and judges each operation with its own permitted crash-state predicates.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "tests" / "wp10_subset_r1" / "model.py"
BLOCK = 512
SEEDS = (1, 183, 3647685189)       # the package's recorded seeds (README: 67 records/seed)


def load_model():
    spec = importlib.util.spec_from_file_location("wp10_subset_model", MODEL_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MODEL = load_model()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    return sha(Path(p).read_bytes())


class Worker:
    """One persistent worker process speaking the tab-delimited protocol."""

    def __init__(self, argv: list[str]):
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def ask(self, *fields: str) -> dict:
        self.proc.stdin.write("\t".join(fields) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError(f"worker ended on {fields[0]} (exit {self.proc.poll()})")
        return json.loads(line)

    def close(self) -> int:
        try:
            self.proc.stdin.write("D\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            pass
        return self.proc.wait()


def read_trace(path: Path) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def image_blocks(image: bytes) -> dict:
    return {i: image[i * BLOCK:(i + 1) * BLOCK] for i in range(len(image) // BLOCK)}


def replay(initial: bytes, trace: list[dict]):
    """Feed the actual history into the model, one actual call at a time. A failed or cut
    call is attempted (every logged unit eligible to persist) and visible nowhere, which
    is what the worker's working image did."""
    dev = MODEL.Device(image_blocks(initial))
    i = 0
    while i < len(trace):
        r = trace[i]
        if r["t"] == "W":
            call = [r]
            while i + 1 < len(trace) and trace[i + 1]["t"] == "W" and trace[i + 1]["call"] == r["call"]:
                i += 1
                call.append(trace[i])
            lbas = [u["lba"] for u in call]
            if lbas != list(range(lbas[0], lbas[0] + len(lbas))) or len({u["ack"] for u in call}) != 1:
                raise ValueError(f"call {r['call']}: units are not one contiguous, uniformly acknowledged call")
            ids = [u["id"] for u in call]
            if ids[0] != dev.next_id or ids != list(range(ids[0], ids[0] + len(ids))):
                raise ValueError(f"call {r['call']}: event IDs {ids} do not continue the model's {dev.next_id}")
            data = b"".join(bytes.fromhex(u["hex"]) for u in call)
            if call[0]["ack"]:
                dev.write(lbas[0], data, acknowledged=True)
            else:
                dev.write(lbas[0], data, acknowledged=False, visible=[])
        elif r["t"] == "F":
            dev.flush(successful=r["ok"])
        i += 1
    return dev


def plans(events: list) -> tuple[str, list[dict]]:
    if len(events) <= MODEL.EXHAUSTIVE_LIMIT:
        return "exhaustive", list(MODEL.exhaustive(events))
    out = []
    for s in SEEDS:
        out.extend(MODEL.sampled(events, s))
    return "sampled", out


def materialize(dev, order: list[int], nblocks: int) -> bytes:
    img = dev.crash_image(order)
    return b"".join(img.get(i, bytes(BLOCK)) for i in range(nblocks))


def projection(dev, order: list[int], durable: bytes, touched: list[int]) -> bytes:
    """materialize(), fast: the model's own crash_image(order) result, written over the
    durable bytes at the epoch's touched LBAs only. crash_image starts from a copy of the
    durable image and changes only LBAs of selected epoch events, so every other block is
    the durable block; the bytes are identical to materialize()."""
    img = dev.crash_image(order)
    buf = bytearray(durable)
    zero = bytes(BLOCK)
    for lba in touched:
        buf[lba * BLOCK:(lba + 1) * BLOCK] = img.get(lba, zero)
    return bytes(buf)


# ---- generic campaign over any worker binding -------------------------------------------
#
# A binding module supplies:
#   NAME                                   evidence label
#   scenarios(only) -> [key tuple]         the accepted crash scenarios of that suite
#   make_worker(tmp) -> worker             with .ask(*fields) and .close()
#   s_run(w, tmp, key, base, cut_unit, cut_flush, err_call, err_flush)
#       -> (worker result dict, trace rows, initial image bytes)
#       base is None (the scenario's own fixture) or a path holding a full image
#   remount(w, tmp, key, image) -> raw observation dict
#   remount_key(key) -> str                any part of the key that changes the remount
#                                          (e.g. a side); images are remounted once per value
#   worker_path                            the built worker, hashed into the summary

import gzip
import shutil
import tempfile


INLINE_LIMIT = 256   # epochs up to this many events keep every event, mask and order inline


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


class Campaign:
    """Runs coordinates, replays them into the model, remounts every distinct projection.

    Evidence (per process part): runs.jsonl, remounts.jsonl, snapshots.jsonl, traces/,
    initial/. Representation, so a large campaign stays retainable without losing a fact:
      * a run's actual trace is stored whole the first time; a cut run whose actual trace is
        the scenario's complete actual trace up to record k plus its own CUT record (checked
        here, record by record) is stored as that reference; anything else is stored whole;
      * a remount's raw snapshot is stored once in snapshots.jsonl by the SHA-256 of its
        canonical JSON; each remount row cites it;
      * an epoch of at most INLINE_LIMIT events keeps every event and every mask and landing
        order inline; a longer one keeps the event-list SHA-256 and first/last IDs (the events
        are the retained trace's), and each sampled projection keeps seed, draw, selected
        count and the SHA-256 of its actual mask and landing order: model.sampled() regenerates
        both from the retained events (replay_run.py checks the hashes)."""

    def __init__(self, binding, evidence: Path, worker, tmp: Path):
        self.b, self.ev, self.w, self.tmp = binding, evidence, worker, tmp
        (evidence / "traces").mkdir(parents=True, exist_ok=True)
        (evidence / "initial").mkdir(parents=True, exist_ok=True)
        self.runs = open(evidence / "runs.jsonl", "w")
        self.remounts = open(evidence / "remounts.jsonl", "w")
        self.snaps = open(evidence / "snapshots.jsonl", "w")
        self.seen, self.snap_seen = set(), set()
        self.refs = {}        # (key, initial sha) -> (trace rows, trace sha)
        self.n_runs = self.n_proj = 0

    def remount(self, key, image: bytes) -> str:
        h, rk = sha(image), self.b.remount_key(key)
        if (h, rk) not in self.seen:
            obs = self.b.remount(self.w, self.tmp, key, image)
            for k in ("image_snapshot", "after_mount_snapshot"):
                if k in obs:
                    obs[k] = self._snapshot_ref(obs[k])
            obs["projection_sha256"] = h
            obs["remount_key"] = rk
            self.remounts.write(json.dumps(obs, sort_keys=True) + "\n")
            self.seen.add((h, rk))
        return h

    # Small per-image fields stay inline; the metadata part of a snapshot (superblocks,
    # index slots) is stored once by hash. Recombining the two gives the worker's snapshot.
    INLINE_SNAPSHOT_KEYS = ("chunk_sha256", "image_sha256")

    def _snapshot_ref(self, snap: dict) -> dict:
        inline = {k: snap[k] for k in self.INLINE_SNAPSHOT_KEYS if k in snap}
        rest = {k: v for k, v in snap.items() if k not in inline}
        ss = sha(_canon(rest))
        if ss not in self.snap_seen:
            self.snaps.write(json.dumps({"snapshot_sha256": ss, "snapshot": rest}, sort_keys=True) + "\n")
            self.snap_seen.add(ss)
        return {"metadata_snapshot_sha256": ss, **inline}

    def _store_trace(self, raw: bytes, tsha: str):
        p = self.ev / "traces" / f"{tsha}.jsonl.gz"
        if not p.exists():
            with gzip.open(p, "wb", compresslevel=6) as f:
                f.write(raw)

    def _trace_ref(self, key, base, isha, trace):
        """How this run's actual trace is retained (see the class docstring)."""
        raw = "".join(json.dumps(r, sort_keys=True) + "\n" for r in trace).encode()
        tsha = sha(raw)
        rk = (key, isha)
        if rk not in self.refs:
            cres, ctrace, _ = self.b.s_run(self.w, self.tmp, key, base, "-", "-", "-", "-")
            craw = "".join(json.dumps(r, sort_keys=True) + "\n" for r in ctrace).encode()
            self.refs[rk] = (ctrace, sha(craw))
            self._store_trace(craw, sha(craw))
        ctrace, csha = self.refs[rk]
        if tsha == csha:
            return {"trace_sha256": tsha, "stored": "whole"}
        if trace and trace[-1]["t"] == "CUT":
            k = len(trace) - 1
            cut_call = trace[-1].get("call")      # None for a cut at a barrier's entry

            def same(a, b):
                if a == b:
                    return True
                # the interrupted call's attempted units: unacknowledged here, acknowledged
                # in the complete run, otherwise identical
                return (a["t"] == b["t"] == "W" and a["call"] == cut_call and not a["ack"]
                        and b["ack"] and dict(a, ack=True) == b)
            if k <= len(ctrace) and all(same(trace[i], ctrace[i]) for i in range(k)):
                return {"trace_sha256": tsha, "stored": "prefix", "reference_trace_sha256": csha,
                        "prefix_records": k, "cut_record": trace[-1],
                        "unacknowledged_cut_call_units": sum(1 for x in trace[:k] if x["t"] == "W"
                                                             and x["call"] == cut_call and not x["ack"])}
        self._store_trace(raw, tsha)
        return {"trace_sha256": tsha, "stored": "whole"}

    def run(self, key, base=None, cut_unit="-", cut_flush="-", err_call="-", err_flush="-",
            label=None, extra=None):
        res, trace, initial = self.b.s_run(self.w, self.tmp, key, base, cut_unit, cut_flush, err_call, err_flush)
        self.last_trace = trace
        isha = sha(initial)
        ip = self.ev / "initial" / f"{isha}.img.gz"
        if not ip.exists():
            with gzip.open(ip, "wb", compresslevel=6) as f:
                f.write(initial)
        tref = self._trace_ref(key, base, isha, trace)
        dev = replay(initial, trace)
        kind, plan = plans(dev.events)
        nblocks = len(initial) // BLOCK
        durable = materialize(dev, [], nblocks)
        touched = sorted({e.lba for e in dev.events if e.lba < nblocks})
        inline = len(dev.events) <= INLINE_LIMIT
        proj, full = [], []
        for p in plan:
            h = self.remount(key, projection(dev, p["landing_order"], durable, touched))
            full.append({**p, "image_sha256": h})
            if inline:
                proj.append({**p, "image_sha256": h})
            else:
                q = {k: v for k, v in p.items() if k not in ("mask", "landing_order")}
                q.update({"selected": len(p["landing_order"]), "mask_sha256": sha(p["mask"].encode()),
                          "landing_order_sha256": sha(_canon(p["landing_order"])), "image_sha256": h})
                proj.append(q)
        lbas = [e.lba for e in dev.events]
        evs = [{"id": e.id, "call": e.call, "lba": e.lba, "ack": e.acknowledged, "sha256": sha(e.data)}
               for e in dev.events]
        epoch = {"length": len(dev.events), "repeated_lba_events": len(lbas) - len(set(lbas)),
                 "barrier_results": dev.flush_results, "durable_sha256": sha(durable),
                 "events_sha256": sha(_canon(evs))}
        if inline:
            epoch["events"] = evs
        elif evs:
            epoch.update({"first_id": evs[0]["id"], "last_id": evs[-1]["id"]})
        row = {"format": "WP10-SUBSET-RUN-ROW-1", "binding": self.b.NAME, "label": label, "scenario": list(key),
               "base": "fixture" if base is None else "projection:" + isha,
               "coordinate": {"cut_op_unit": cut_unit, "cut_op_barrier_entry": cut_flush,
                              "error_op_call": err_call, "error_op_barrier": err_flush},
               "worker": res, "trace": tref, "initial_sha256": isha,
               "remount_key": self.b.remount_key(key), "epoch": epoch,
               "plan": kind, "projections_inline": inline, "projections": proj,
               "distinct_images": len({q["image_sha256"] for q in proj})}
        if extra:
            row["second_cut_of"] = extra
        self.runs.write(json.dumps(row, sort_keys=True) + "\n")
        self.n_runs += 1
        self.n_proj += len(proj)
        return res, dev, full

    def close(self):
        self.runs.close()
        self.remounts.close()
        self.snaps.close()


# ---- the bounded unit-boundary plan (Verification #186, "long-epoch scale") ---------------
#
# For an operation with U actual units, the union (deduplicated, clamped into 0..U) of:
#   0..8 and max(0, U-8)..U;  2^k-1, 2^k, 2^k+1 for every power of two <= U;
#   1024j-1, 1024j, 1024j+1 for every positive 1024j <= U;
#   every metadata/identity/index write boundary (each such call's first and end unit
#   boundary) and the boundaries adjacent to it;  every barrier entry's unit boundary and
#   its two neighbours.
# Unit boundary k is the cut after k units. A metadata/identity/index unit is one outside the
# chunk area of the public layout (engine/include/tape.h: below TAPE_LBA_CHUNK_BASE, or the
# mirror superblock in the last block). Error writes: every call that contains a unit next to
# a selected boundary, and every metadata/identity/index call. Barrier entries and barrier
# errors: all. The selection is unit-coordinate SAMPLING of a long copy, never every boundary.

TAPE_LBA_CHUNK_BASE = 2048


def boundary_plan(trace: list[dict], nblocks: int) -> dict:
    units = [r for r in trace if r["t"] == "W"]
    U = len(units)
    want = set(range(0, 9)) | set(range(max(0, U - 8), U + 1))
    k = 1
    while k <= U:
        want |= {k - 1, k, k + 1}
        k *= 2
    for j in range(1024, U + 1, 1024):
        want |= {j - 1, j, j + 1}
    calls, meta_calls = {}, set()
    for i, u in enumerate(units):
        calls.setdefault(u["call"], []).append(i)
        if u["lba"] < TAPE_LBA_CHUNK_BASE or u["lba"] == nblocks - 1:
            meta_calls.add(u["call"])
    for c in meta_calls:
        first, end = calls[c][0], calls[c][-1] + 1
        want |= {first - 1, first, first + 1, end - 1, end, end + 1}
    n = 0
    for r in trace:
        if r["t"] == "W":
            n += 1
        elif r["t"] == "F":
            want |= {n - 1, n, n + 1}
    cuts = sorted(x for x in want if 0 <= x <= U)
    call_of = [u["call"] for u in units]
    err_calls = set(meta_calls)
    for x in cuts:
        for i in (x - 1, x):
            if 0 <= i < U:
                err_calls.add(call_of[i])
    order = sorted(calls)          # error_write coordinates are call ordinals, as in tasks()
    return {"plan": "v186-bounded", "label": "SAMPLED unit coordinates (not every boundary)",
            "op_units": U, "cut_units": cuts,
            "error_write_calls": sorted(order.index(c) for c in err_calls),
            "metadata_calls": len(meta_calls), "barriers": sum(1 for r in trace if r["t"] == "F")}


def selected(key, only, exclude=None) -> bool:
    """--only / --exclude: comma-separated prefixes of the "/"-joined scenario key."""
    k = "/".join(map(str, key))
    if only and not any(k.startswith(p) for p in only.split(",")):
        return False
    return not (exclude and any(k.startswith(p) for p in exclude.split(",")))


def tasks(counts: dict, second: int, bounded: dict | None = None) -> list:
    """Every run coordinate, in a fixed order, so shards partition the campaign exactly.
    With a bounded plan for a key, its unit cuts and error writes are the plan's."""
    out = []
    for key, (u, b, k) in counts.items():
        bp = (bounded or {}).get(key)
        out.append((key, "complete", None))
        out += [(key, "cut_unit", i) for i in (bp["cut_units"] if bp else range(u + 1))]
        out += [(key, "cut_barrier_entry", j) for j in range(b)]
        out += [(key, "error_write", j) for j in (bp["error_write_calls"] if bp else range(k))]
        out += [(key, "error_barrier", j) for j in range(b)]
        out += [(key, "second", n) for n in range(second)]
    return out


def bounded_bases(c: Campaign, key, cuts: list):
    """Two DISTINCT first-cut durable bases for the bounded plan: the first distinct image
    over the selected boundaries in order, and the first distinct LATER-ONLY projection (a
    later event persisted while an earlier one did not), else the next distinct image.
    Recomputed from actual runs. Returns the bases found (possibly fewer than two) and every
    distinct image identity enumerated."""
    first, later, nxt, seen = None, None, None, {}
    for i in cuts:
        _, dev, proj = c.run(key, cut_unit=i, label="first_cut_for_second")
        ids = [e.id for e in dev.events]
        for q in proj:
            h = q["image_sha256"]
            if h in seen:
                continue
            sel = set(q["landing_order"])
            lo = bool(sel) and any(e not in sel and e < max(sel) for e in ids)
            seen[h] = {"first_cut_op_unit": i, "later_only": lo}
            item = (i, q, materialize(dev, q["landing_order"], len(dev.durable)), lo)
            if first is None:
                first = item
            elif lo and later is None:
                later = item
            elif nxt is None:
                nxt = item
        if first is not None and later is not None:
            break
    bases = [b for b in (first, later or nxt) if b is not None]
    return bases, seen


def first_cut_base(c: Campaign, key, u: int, n: int):
    """The n-th distinct durable image reached by first cuts at unit boundaries 0, 1, ...,
    in plan order (recomputed from actual runs, never shared between processes)."""
    seen = {}
    for i in range(u + 1):
        _, dev, proj = c.run(key, cut_unit=i, label="first_cut_for_second")
        for q in proj:
            if q["image_sha256"] not in seen:
                seen[q["image_sha256"]] = (i, q, materialize(dev, q["landing_order"], len(dev.durable)))
                if len(seen) > n:
                    return list(seen.values())[n]
    return None


def do_task(c: Campaign, tmp: Path, task, counts: dict, bounded: dict | None = None) -> None:
    key, kind, x = task
    why = getattr(c.b, "unreachable", lambda k, kd, v: None)(key, kind, x)
    if why:
        # A coordinate the existing route cannot produce: recorded as a bound, never faked.
        c.runs.write(json.dumps({"format": "WP10-SUBSET-RUN-ROW-1", "binding": c.b.NAME, "label": kind,
                                 "scenario": list(key), "coordinate_index": x, "not_reachable": why},
                                sort_keys=True) + "\n")
        return
    if kind == "complete":
        c.run(key, label="complete")
    elif kind == "cut_unit":
        c.run(key, cut_unit=x, label="cut_unit")
    elif kind == "cut_barrier_entry":
        c.run(key, cut_flush=x, label="cut_barrier_entry")
    elif kind == "error_write":
        c.run(key, err_call=x, label="error_write")
    elif kind == "error_barrier":
        c.run(key, err_flush=x, label="error_barrier")
    elif kind == "second" and (bounded or {}).get(key):
        # Bounded plan: one of two DISTINCT first-cut bases, RAM destroyed (a fresh run from
        # the base's bytes only), and the same bounded plan applied to the second run's own
        # actual trace. Fewer than two distinct bases is recorded, never duplicated.
        bases, seen = bounded_bases(c, key, bounded[key]["cut_units"])
        if x >= len(bases):
            c.runs.write(json.dumps({"format": "WP10-SUBSET-RUN-ROW-1", "binding": c.b.NAME, "label": "second",
                                     "scenario": list(key), "coordinate_index": x,
                                     "not_available": "only %d distinct first-cut base(s) exist over the bounded plan"
                                                      % len(bases),
                                     "enumerated_first_cut_images": seen}, sort_keys=True) + "\n")
            return
        i, q, img, lo = bases[x]
        p = tmp / "second-base.img"
        p.write_bytes(img)
        tag = {"first_cut_op_unit": i, "first_mask": q["mask"], "first_landing_order": q["landing_order"],
               "first_image_sha256": q["image_sha256"], "second_base_index": x, "later_only": lo,
               "base_selection": "first distinct" if x == 0 else ("later-only" if lo else "next distinct")}
        r2, dev2, _ = c.run(key, base=p, label="second_complete", extra=tag)
        if r2.get("setup_ok", True):
            bp2 = boundary_plan(c.last_trace, len(img) // BLOCK)
            tag["second_plan"] = {k: v for k, v in bp2.items() if k != "cut_units"}
            tag["second_plan"]["cut_units_sha256"] = sha(_canon(bp2["cut_units"]))
            for j in bp2["cut_units"]:
                c.run(key, base=p, cut_unit=j, label="second_cut", extra=tag)
    elif kind == "second":
        # Second interruption after actual recovery: a fresh run of the same operation whose
        # base is a first-cut projection's durable bytes only, cut at every unit again.
        got = first_cut_base(c, key, counts[key][0], x)
        if got is None:
            return
        i, q, img = got
        p = tmp / "second-base.img"
        p.write_bytes(img)
        tag = {"first_cut_op_unit": i, "first_mask": q["mask"], "first_landing_order": q["landing_order"],
               "first_image_sha256": q["image_sha256"], "second_base_index": x}
        r2, _, _ = c.run(key, base=p, label="second_complete", extra=tag)
        if r2.get("setup_ok", True):
            for j in range(r2["op_units"] + 1):
                c.run(key, base=p, cut_unit=j, label="second_cut", extra=tag)


def _run_part(args) -> dict:
    modname, evidence, part, counts, second, bounded = args
    binding = importlib.import_module(modname)
    tmp = Path(tempfile.mkdtemp())
    try:
        w = binding.make_worker(tmp)
        c = Campaign(binding, evidence, w, tmp)
        for t in part:
            do_task(c, tmp, t, counts, bounded)
        c.close()
        return {"worker_exit": w.close(), "runs": c.n_runs, "projections": c.n_proj,
                "distinct_remounted_images": len(c.seen), "tasks": len(part)}
    finally:
        shutil.rmtree(tmp)


def campaign_main(binding, argv=None) -> int:
    import argparse
    import multiprocessing as mp
    import sys
    ap = argparse.ArgumentParser(description=binding.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--only", help="comma-separated scenario key prefixes to run")
    ap.add_argument("--exclude", help="comma-separated scenario key prefixes to leave out")
    ap.add_argument("--second-cut", type=int, default=2, help="first-cut images re-run per scenario")
    ap.add_argument("--shard", default="0/1", help="I/N: run the tasks whose index %% N == I")
    ap.add_argument("--jobs", type=int, default=1, help="parallel worker processes in this shard")
    ap.add_argument("--unit-plan", choices=("every", "v186"), default="every",
                    help="every unit boundary, or Verification #186's bounded boundary set")
    a = ap.parse_args(argv)
    si, sn = (int(v) for v in a.shard.split("/"))
    a.evidence.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    try:
        w = binding.make_worker(tmp)
        counts, bounded = {}, {}
        for key in [k for k in binding.scenarios(None) if selected(k, a.only, a.exclude)]:
            r, tr, init = binding.s_run(w, tmp, key, None, "-", "-", "-", "-")
            counts[key] = (r["op_units"], r["op_barriers"], r["op_calls"])
            if a.unit_plan == "v186":
                bounded[key] = boundary_plan(tr, len(init) // BLOCK)
        w.close()
    finally:
        shutil.rmtree(tmp)
    allt = tasks(counts, a.second_cut, bounded)
    mine = [t for n, t in enumerate(allt) if n % sn == si]
    jobs = [(binding.__name__, a.evidence / f"part-{si:03d}-{j:02d}", mine[j::a.jobs], counts, a.second_cut, bounded)
            for j in range(a.jobs)]
    if sys.path[0] not in os.environ.get("PYTHONPATH", ""):
        os.environ["PYTHONPATH"] = os.pathsep.join([str(Path(binding.__file__).resolve().parent),
                                                    os.environ.get("PYTHONPATH", "")])
    if a.jobs == 1:
        res = [_run_part(jobs[0])]
    else:
        with mp.get_context("spawn").Pool(a.jobs) as pool:
            res = pool.map(_run_part, jobs)
    import time as _t
    summary = {"format": "WP10-SUBSET-SUMMARY-1", "binding": binding.NAME, "shard": a.shard,
               "unit_plan": a.unit_plan,
               "bounded_plans": {"/".join(map(str, k)): dict(v, cut_units_count=len(v["cut_units"]))
                                 for k, v in bounded.items()},
               "only": a.only, "exclude": a.exclude,
               "tasks_total": len(allt), "tasks_this_shard": len(mine), "parts": res,
               "scenarios": {"/".join(map(str, k)): {"op_units": v[0], "op_barriers": v[1], "op_calls": v[2]}
                             for k, v in counts.items()},
               "second_cut_bases_per_scenario": a.second_cut, "seeds": list(SEEDS),
               "model_sha256": sha_file(MODEL_PATH), "worker_sha256": sha_file(binding.worker_path)}
    (a.evidence / f"summary-{si:03d}.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"binding": binding.NAME, "shard": a.shard, "tasks": len(mine),
                      "runs": sum(r["runs"] for r in res), "projections": sum(r["projections"] for r in res),
                      "worker_exits": [r["worker_exit"] for r in res]}))
    return 0 if all(r["worker_exit"] == 0 for r in res) else 1
