#!/usr/bin/env python3
"""Binding self-proofs ADAPTER.md asks for before any campaign (Product #440), on the
existing WP-10 core worker. Each proof prints PASS/FAIL and the facts behind it; the run
writes binding-proofs.json. These prove the transport, not any operation outcome.

  P1 (a,B): a later event lands while an earlier one does not, in actual worker bytes.
  P2 reverse-order repeated-LBA persistence: the older version wins when it lands last.
  P3 fresh second remount: R carries nothing between images.
  P4 all/none: the all-landed and none-landed projections at a cut equal the old
     write_through and flush_required durable images of the old C command.
  P5 barrier epochs: a successful barrier ends the epoch; a failed one does not.
  P6 dropped barrier / early identity: replaying the setup barrier that made a recorded
     chunk durable as dropped lets the index (identity) land before its chunk data, and the
     existing raw-state predicate (crash_core_draft8 media.require_chunk_hashes_equal) goes
     red; the honest replay of the same actual history never does.
  P7 (observation only) a dropped barrier inside one index slot, under the existing
     logical fingerprint: reported, not counted, because a mixed slot is lawfully old.
"""
from __future__ import annotations

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
import run_core as rc  # noqa: E402
import media  # noqa: E402  (verifier package, unchanged)

RESULTS = []


def proof(name, ok, **facts):
    RESULTS.append({"proof": name, "pass": bool(ok), **facts})
    print(("PASS " if ok else "FAIL ") + name + "  " + json.dumps(facts, sort_keys=True)[:300])


def S(w, tmp, key, cut_unit="-", cut_flush="-", err_call="-", err_flush="-", base="-"):
    tr, init = tmp / "t.jsonl", tmp / "i.img"
    res = w.ask("S", *key, base, str(cut_unit), str(cut_flush), str(err_call), str(err_flush), str(tr), str(init))
    return res, sd.read_trace(tr), init.read_bytes()


def R(w, tmp, img, side="B"):
    p = tmp / "r.img"
    p.write_bytes(img)
    return w.ask("R", str(p), side)


def block(img, lba):
    return img[lba * sd.BLOCK:(lba + 1) * sd.BLOCK]


def replay_dropping(initial, trace, drop):
    """Replay with the barriers whose trace ordinal is in `drop` treated as not persisted
    (a deliberately faulty device), everything else exactly as actual."""
    t2 = [dict(r, ok=False) if r["t"] == "F" and r["ord"] in drop else r for r in trace]
    return sd.replay(initial, t2)


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    try:
        w = rc.fixture_worker(tmp)
        nb = None

        # P1: respool writes single-block chunk units with no barrier between them.
        key = ("stage_clear", "respool", "-")
        res, tr, init = S(w, tmp, key, cut_unit=12)
        nb = len(init) // sd.BLOCK
        dev = sd.replay(init, tr)
        ev = dev.events
        a, b = ev[0], ev[-1]
        order = [b.id]                                   # B landed, a not
        img = sd.materialize(dev, order, nb)
        obs = R(w, tmp, img)
        proof("P1 (a,B) in actual worker bytes",
              len(ev) >= 2 and a.lba != b.lba and block(img, b.lba) == b.data
              and block(img, a.lba) == block(init, a.lba) != a.data
              and obs["image_snapshot"]["image_sha256"] == sd.sha(img),
              epoch_events=len(ev), a_lba=a.lba, B_lba=b.lba, image_sha256=sd.sha(img))

        # P2: the real core traces never write one LBA twice inside an epoch (reported by the
        # campaign); prove the transport keeps versions with an actual-format history.
        lba = ev[0].lba
        v1, v2 = bytes([0x11]) * sd.BLOCK, bytes([0x22]) * sd.BLOCK
        base_id = 0
        synth = [{"t": "W", "id": base_id, "call": 0, "lba": lba, "ack": True, "phase": "op", "hex": v1.hex()},
                 {"t": "W", "id": base_id + 1, "call": 1, "lba": lba, "ack": True, "phase": "op", "hex": v2.hex()}]
        d2 = sd.replay(init, synth)
        rev = sd.materialize(d2, [1, 0], nb)             # newer lands first, older last
        fwd = sd.materialize(d2, [0, 1], nb)
        o_rev = R(w, tmp, rev)
        proof("P2 reverse-order repeated-LBA: older version persists",
              block(rev, lba) == v1 and block(fwd, lba) == v2
              and o_rev["image_snapshot"]["image_sha256"] == sd.sha(rev),
              lba=lba, reverse_image_sha256=sd.sha(rev), forward_image_sha256=sd.sha(fwd))

        # P3: R(X), R(Y), R(X) — the second X is byte-for-byte the first.
        x1 = R(w, tmp, img)
        y = R(w, tmp, rev)
        x2 = R(w, tmp, img)
        proof("P3 fresh second remount carries no state", x1 == x2 and x1 != y,
              x_result=x1["remount_result"], y_result=y["remount_result"])

        # P4: all/none at the start of each old before_write ordinal equal the old modes.
        mism, checked = [], 0
        for fam, var, seed in rc.scenarios():
            res0, tr0, init0 = S(w, tmp, (fam, var, seed))
            units_before = []
            n = 0
            calls = {}
            for r in tr0:
                if r["t"] == "W" and r["phase"] == "op":
                    calls.setdefault(r["call"], 0)
                    calls[r["call"]] += 1
            for c in sorted(calls):
                units_before.append(n)
                n += calls[c]
            scope = "closure" if seed != "-" else "first"
            for ordinal, ub in enumerate(units_before):
                _, trc, initc = S(w, tmp, (fam, var, seed), cut_unit=ub)
                dc = sd.replay(initc, trc)
                ids = [e.id for e in dc.events if e.acknowledged]   # the old modes never land a failed write
                img_all = sd.sha(sd.materialize(dc, ids, nb))
                img_none = sd.sha(sd.materialize(dc, [], nb))
                old = {}
                for mode in ("write_through", "flush_required"):
                    o = w.ask("C", "0", scope, fam, var, mode, "before_write", str(ordinal), "0", seed)
                    old[mode] = o["post_snapshot"]["image_sha256"]
                checked += 1
                if (old["write_through"], old["flush_required"]) != (img_all, img_none):
                    mism.append({"scenario": [fam, var, seed], "ordinal": ordinal,
                                 "old": old, "subset_all": img_all, "subset_none": img_none})
        proof("P4 all/none equal old write_through/flush_required", not mism and checked > 0,
              coordinates=checked, mismatches=mism[:5])

        # P5: barrier epochs on actual record_commit histories.
        key = ("record_commit", "overwrite", "-")
        _, trc, initc = S(w, tmp, key)
        dc = sd.replay(initc, trc)
        _, tre, inite = S(w, tmp, key, err_flush=0)      # the first op barrier fails
        de = sd.replay(inite, tre)
        failed_ids = [e.id for e in de.events]
        proof("P5 successful barrier ends the epoch; failed does not",
              dc.events == [] and dc.flush_results == [True, True, True]
              and False in de.flush_results and 1 in failed_ids,
              complete_epoch=len(dc.events), error_epoch_ids=failed_ids, error_barriers=de.flush_results)

        # P6 dropped barrier, judged by the existing chunk-preservation predicate. pre is the
        # durable snapshot at operation start (setup's barrier actually succeeded).
        pre_img = sd.materialize(sd.replay(initc, [r for r in trc if r.get("phase") == "setup"]), [], nb)
        pre = R(w, tmp, pre_img)["image_snapshot"]

        def chunk_red(dev):
            red = 0
            kind, plan = sd.plans(dev.events)
            for p in plan:
                post = R(w, tmp, sd.materialize(dev, p["landing_order"], nb))["image_snapshot"]
                try:
                    media.require_chunk_hashes_equal(pre, post)
                except Exception:
                    red += 1
            return red, len(plan)
        # cut at the entry of the first operation barrier: the index body (393) is attempted
        _, trb, initb = S(w, tmp, key, cut_flush=0)
        honest_red, honest_n = chunk_red(sd.replay(initb, trb))
        setup_barrier = [r["ord"] for r in trb if r["t"] == "F" and r["phase"] == "setup"]
        dropped_red, dropped_n = chunk_red(replay_dropping(initb, trb, set(setup_barrier)))
        proof("P6 dropped barrier / early identity: index before its chunk turns the existing chunk predicate red",
              honest_red == 0 and dropped_red > 0,
              honest=[honest_red, honest_n], dropped=[dropped_red, dropped_n], dropped_barriers=setup_barrier)

        # P7 early identity: drop the barrier between the slot body (393) and its identity
        # block (392); the existing fingerprint must then leave {old, new} for some image.
        fp_old = media.logical_fingerprint(pre, requested_side="B")
        fp_new = media.logical_fingerprint(R(w, tmp, sd.materialize(dc, [], nb))["image_snapshot"], requested_side="B")
        op_barrier = [r["ord"] for r in trc if r["t"] == "F" and r["phase"] == "op"][:1]

        def fp_out(dev):
            out, n = 0, 0
            kind, plan = sd.plans(dev.events)
            for p in plan:
                n += 1
                fp = media.logical_fingerprint(R(w, tmp, sd.materialize(dev, p["landing_order"], nb))["image_snapshot"],
                                               requested_side="B")
                out += fp not in (fp_old, fp_new)
            return out, n
        cut_after = S(w, tmp, key, cut_flush=1)
        dcut = sd.replay(cut_after[2], cut_after[1])
        honest_out = fp_out(dcut)
        dropped_out = fp_out(replay_dropping(cut_after[2], cut_after[1], set(op_barrier)))
        # Observation, not a pass/fail proof: inside one index slot a dropped barrier gives
        # mixed body/identity images, and the existing fingerprint keeps every one of them at
        # old or new (the slot check reverts a mixed slot). It is therefore not a detecting
        # control; P6 is.
        RESULTS.append({"proof": "P7 observation: dropped in-slot barrier", "pass": None,
                        "honest_outside_old_new": list(honest_out), "dropped_outside_old_new": list(dropped_out),
                        "fp_old_new_differ": fp_old != fp_new})
        print("INFO P7 dropped in-slot barrier: outside old/new", dropped_out, "honest", honest_out)

        rcw = w.close()
        ok = all(r["pass"] for r in RESULTS if r["pass"] is not None) and rcw == 0
        out = {"format": "WP10-SUBSET-BINDING-PROOFS-1", "worker_exit": rcw, "proofs": RESULTS,
               "model_sha256": sd.sha_file(sd.MODEL_PATH), "worker_sha256": sd.sha_file(rc.WORKER)}
        dest = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "binding-proofs.json"
        dest.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
        print("binding proofs:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    sys.exit(main())
