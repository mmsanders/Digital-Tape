#!/usr/bin/env python3
"""Synthetic public-observation emitter for WP-10 backlog rows 1-3. Verifier self-test only."""
from __future__ import annotations

import gzip
import hashlib
import json
import sys

import dupfrag as D
import oracle as O

MUTANTS = {
    # row 1
    "layout_preserving": 1, "fragment_order": 1,
    # row 2
    "frontier_other_generation": 2, "ignores_a_high_water": 2, "format_empty_b_frontier": 2,
    # row 3
    "service_writes_live_chunk": 3, "service_commits_index": 3, "service_missing_final_flush": 3,
    "frontier_counts_uncommitted_audio": 3,
}
ROW1_TX = {"layout_preserving", "fragment_order"}


def _mount(img, side, writable):
    c = D.classify(img, side, writable)
    out = {"result": c["result"][0], "repair_events": []}
    if out["result"] != "TAPE_OK":
        return out
    out["info"] = {"uuid": c["uuid"], "free_chunks": c["free_chunks"], "total_frames": c["total_frames"],
                   "entry_count": c["entry_count"], "side_b_valid": c["side_b_valid"],
                   "needs_repair": c["needs_repair"]}
    if c["repair"]:
        out["repair_events"] = [{"op": "write", "lba": c["repair"][0], "count": 1,
                                 "data_sha256": O.sha(c["repair"][1])}, {"op": "flush"}]
    if side == "A" and writable:
        out["pcm_sha256"] = D.rendered_sha256(img, c["layout"])
    return out


def row1(case, mutant):
    tx = mutant if mutant in ROW1_TX else None
    inject = tuple(case["inject"]) if case["kind"] == "crash" else None
    prefix = O.planned_prefix(case["scenario"], inject, tx)
    src = hashlib.sha256(b"synthetic fragmented C-90 source").hexdigest()
    obs = {"scenario": case["scenario"], "source_sha256_before": src, "source_sha256_after": src,
           "trace_sha256": O.sha(O.canonical(O.trace_events(prefix)).encode()),
           "dst_chunk_lbas": O.dst_chunk_lbas(prefix)}
    if inject is None:
        img = D.completed_image(case["scenario"], tx)
        obs["call"] = {"fn": "tape_dup", "result": "TAPE_OK", "more_work": False}
    else:
        images = D.possible_images(case["scenario"], inject, case["mode"], tx)
        img = images[case["index"] % len(images)]
        obs.update(mode=case["mode"], inject=case["inject"], fired=True)
    obs["durable_sha256"] = O.durable_digest(img)
    obs["ro_A"], obs["rw_A"], obs["rw_B"] = _mount(img, "A", False), _mount(img, "A", True), _mount(img, "B", True)
    return obs


def row2(case, mutant):
    exp = O.row2_expectation(case["campaign"], case["case_index"])
    free = exp["free_chunks"]
    if case["campaign"] == "C69":
        c = O._c69_cases()[case["case_index"]]
        if mutant == "frontier_other_generation" and c["family"] == "record_commit":
            free = 5 - 2 if free == 5 - 3 else 5 - 3
        if mutant == "ignores_a_high_water" and c["family"] in ("record_commit", "reset_b"):
            free += 1
    elif mutant == "format_empty_b_frontier" and free == 4:
        free = 3
    return {"campaign": case["campaign"], "case_index": case["case_index"],
            "post_snapshot_sha256": exp["post_snapshot_sha256"],
            "remount": {"side": exp["side"], "result": exp["result"], "total_chunks": exp["total_chunks"],
                        "free_chunks": free}}


def row3(case, mutant):
    events = []
    for k, lba in enumerate(O.REC_BLOCKS):
        if case["record_mode"] == "overdub":
            events.append({"op": "read", "lba": O.C.fixture.LBA_CHUNK_BASE + k, "count": 1})
        target = O.C.fixture.LBA_CHUNK_BASE + k if (mutant == "service_writes_live_chunk" and k == 0) else lba
        events.append({"op": "write", "lba": target, "count": 1})
        if mutant == "service_commits_index" and k == 2:
            events.append({"op": "write", "lba": O.C.fixture.LBA_B1, "count": 1})
        if not (mutant == "service_missing_final_flush" and k == 2):
            events.append({"op": "flush"})
    writes = [i for i, e in enumerate(events) if e["op"] == "write" and e["lba"] != O.C.fixture.LBA_B1]
    flushes = [i for i, e in enumerate(events) if e["op"] == "flush"]
    pre = O.record_pre()
    crashes = []
    for inj in O.record_injections(len(flushes)):
        pos = writes[inj[1]] if inj[0] == "write" else flushes[inj[1]]
        meta = pre["meta_sha256"]
        chunk0 = pre["chunk0_sha256"]
        if mutant == "service_commits_index" and pos > writes[2]:
            meta = hashlib.sha256(b"B1 header written during service").hexdigest()
        if mutant == "service_writes_live_chunk" and pos >= writes[0] and not (inj == ["write", 0, 0]):
            chunk0 = hashlib.sha256(b"live chunk 0 overwritten").hexdigest()
        free = O.C.fixture.TOTAL_CHUNKS - O.REC_CHUNK - (1 if mutant == "frontier_counts_uncommitted_audio" else 0)
        crashes.append({"inject": inj, "fired": True, "prefix_len": pos + 1, "meta_sha256": meta,
                        "chunk0_sha256": chunk0,
                        "remount": {"side": "B", "result": "TAPE_OK",
                                    "info": {"free_chunks": free, "total_frames": D.CF, "entry_count": 1,
                                             "side_b_valid": True, "needs_repair": False},
                                    "pcm_sha256": pre["pcm_sha256"] if chunk0 == pre["chunk0_sha256"]
                                    else chunk0}})
    return {"record_mode": case["record_mode"], "mode": case["mode"],
            "setup": [{"fn": "tape_mount", "side": "B", "result": "TAPE_OK"},
                      {"fn": "tape_seek", "frame": 0, "result": "TAPE_OK"},
                      {"fn": "tape_arm", "record_mode": case["record_mode"], "result": "TAPE_OK"},
                      {"fn": "tape_feed", "requested": O.REC_FRAMES, "accepted": O.REC_FRAMES,
                       "result": "TAPE_OK", "events_from_call": 0}],
            "clean": {"events": events, "frames_owed_after": False}, "crashes": crashes}


def observation(case, mutant=None):
    if mutant and MUTANTS[mutant] != case["row"]:
        mutant = None
    body = (row1, row2, row3)[case["row"] - 1](case, mutant)
    return {"schema": O.SCHEMA, "index": case["index"], "row": case["row"], "kind": case["kind"], **body}


def lines(mutant=None, rows=None):
    for case in O.iter_cases():
        if rows and case["row"] not in rows:
            continue
        yield json.dumps(observation(case, mutant), sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raw = "".join(line + "\n" for line in lines()).encode("utf-8")
    sys.stdout.buffer.write(gzip.compress(raw, compresslevel=9, mtime=0))
