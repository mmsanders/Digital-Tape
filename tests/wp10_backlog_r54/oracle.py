#!/usr/bin/env python3
"""Independent oracle for WP-10 backlog rows (Verification #116, DRAFT-9)."""
from __future__ import annotations

import functools
import hashlib
import json

import model as M

SCHEMA = "wp10-backlog-r54-observation-v1"
MODES = ("flush_required", "write_through")
ROW1 = "WP10.session.load.mount_repair_write"
ROW2 = "WP10.dup.rerun_completes"
ROW3 = "WP10.dup.destination_shape.mounts_both_sides_high_label"
FORBIDDEN_KEYS = {"verdict", "passed", "permitted", "expected", "outcome_ok", "same_content",
                  "rerun_completed", "row_ok"}
# Row 3 sources: (id, frames, label). Frame counts straddle the ceil(frames / CHUNK_FRAMES) boundary.
ROW3_SOURCES = (("EMPTY", 0, "Blank tape"), ("SHORT", 128, "Grandma's Songs"),
                ("ONE-CHUNK", M.CF, "Exactly one chunk"), ("CHUNK-PLUS-ONE", M.CF + 1, "0123456789abcdefghijklmnopqrstuv"))
ROW3_DESTS = ("blank", "healthy_pair")


def need(ok, why):
    if not ok:
        raise AssertionError(why)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def trace_sha256(ops):
    return M.sha(canonical([{"op": "write", "lba": M.TRACKED[o[1]], "count": 1, "data_sha256": M.sha(o[2])}
                            if o[0] == "w" else {"op": "flush"} for o in ops]).encode())


def _no_verdicts(value, where="observation"):
    if isinstance(value, dict):
        bad = FORBIDDEN_KEYS & set(value)
        need(not bad, f"{where} carries adapter-derived field(s) {sorted(bad)}")
        for k, v in value.items():
            _no_verdicts(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _no_verdicts(v, f"{where}[{i}]")


def mount_expectation(img, side, writable):
    c = M.classify(img, side, writable)
    exp = {"results": list(c["result"])}
    if c["result"] == ("TAPE_OK",):
        exp["info"] = {"uuid": c["uuid"], "free_chunks": c["free_chunks"], "total_frames": c["total_frames"],
                       "entry_count": c["entry_count"], "side_b_valid": c["side_b_valid"],
                       "needs_repair": c["needs_repair"]}
        rep = c["repair"]
        exp["repair_events"] = [] if rep is None else [
            {"op": "write", "lba": rep[0], "count": 1, "data_sha256": M.sha(rep[1])}, {"op": "flush"}]
        if side == "A" and writable:
            exp["pcm_sha256"] = M.rendered_sha256(img, c["layout"])
        exp["after"] = img if rep is None else {**img, ("M" if rep[0] == M.MIRROR else "P"): rep[1]}
    return exp


def check_mount(m, img, side, writable, label):
    exp = mount_expectation(img, side, writable)
    need(isinstance(m, dict) and m.get("result") in exp["results"],
         f"{label}: {m.get('result') if isinstance(m, dict) else m} not in permitted {exp['results']}")
    if m["result"] != "TAPE_OK":
        need("info" not in m and m.get("repair_events") == [], f"{label}: failed mount reported info or wrote")
        return exp
    need(m.get("info") == exp["info"], f"{label}: info {m.get('info')} != {exp['info']}")
    need(m.get("repair_events") == exp["repair_events"], f"{label}: phase-4 repair events")
    if "pcm_sha256" in exp:
        need(m.get("pcm_sha256") == exp["pcm_sha256"], f"{label}: rendered audio is not the selected generation's")
    return exp


# ------------------------------------------------------------------ row 1

def check_row1(case, obs, trust_trace=False):
    base = M.cartridge(*M.REPAIR_SHAPES[case["shape"]])
    ops = M.repair_ops(base)
    inject = tuple(case["inject"])
    need(obs.get("fired") is True, "planned injection did not fire")
    if not trust_trace:
        need(obs.get("repair_trace_sha256") == trace_sha256(M.prefix(ops, inject)),
             "phase-4 repair write/flush trace is not 'rewrite that partner from the candidate; flush'")
    images = {M.digest(i): i for i in M.possible_images(base, ops, inject, case["mode"])}
    img = images.get(obs.get("durable_sha256"))
    need(img is not None, "durable media after the repair crash is not a permitted state")
    before = M.classify(base, "A", False)
    ro = check_mount(obs.get("ro_A"), img, "A", False, "read-only remount")
    rw = check_mount(obs.get("rw_A"), img, "A", True, "writable remount")
    for label, exp in (("read-only", ro), ("writable", rw)):
        need(exp["results"] == ["TAPE_OK"], f"{label}: interrupted repair left a cartridge that does not mount")
        info = exp["info"]
        need(all(info[k] == before[k] for k in ("uuid", "free_chunks", "total_frames", "entry_count")),
             f"{label}: interrupted repair changed the mounted content")
    after = rw["after"]
    need(obs.get("durable_after_rw_sha256") == M.digest(after), "writable remount did not finish the repair exactly")
    for copy in ("P", "M"):
        need(M.sb_valid(after[copy]) and M.gen(after[copy]) == M.gen(M.classify(base, "A", True)["repair"][1]),
             "repair advanced sb_generation")
    need(after["A0h"] == base["A0h"] and after["B0h"] == base["B0h"], "repair advanced an index sequence")


# ------------------------------------------------------------------ row 2

def check_row2(case, obs, trust_trace=False):
    base = M.rerun_destination(case["shape"])
    ops = M.dup_ops(base)
    inject = tuple(case["inject"])
    need(obs.get("fired") is True, "planned injection did not fire")
    if not trust_trace:
        need(obs.get("trace_sha256") == trace_sha256(M.prefix(ops, inject)), "first run trace is not tapefs §9.5")
    images = {M.digest(i): i for i in M.possible_images(base, ops, inject, case["mode"])}
    img = images.get(obs.get("durable_sha256"))
    need(img is not None, "durable media after the interrupted copy is not a permitted state")
    rerun = obs.get("rerun")
    need(isinstance(rerun, dict) and rerun.get("call") == {"fn": "tape_dup", "result": "TAPE_OK", "more_work": False},
         "re-run on the same destination device did not complete")
    rerun_ops = M.dup_ops(img)
    if not trust_trace:
        need(rerun.get("trace_sha256") == trace_sha256(rerun_ops),
             "re-run did not follow tapefs §9.5 from the crashed state (item-5 classification)")
    lbas = rerun.get("dst_chunk_lbas")
    need(isinstance(lbas, list) and set(lbas) <= {M.B.LBA_CHUNK_BASE}, f"re-run addressed chunks {lbas}")
    final = M.apply(img, rerun_ops)
    need(rerun.get("durable_sha256") == M.digest(final) == M.digest(M.apply(base, ops)),
         "re-run did not reach the completed copy")
    check_mount(obs.get("rw_A"), final, "A", True, "completed copy, Side A")
    check_mount(obs.get("rw_B"), final, "B", True, "completed copy, Side B")


# ------------------------------------------------------------------ row 3

def row3_expected(source_id, dest):
    frames, label = next((f, lab) for s, f, lab in ROW3_SOURCES if s == source_id)
    lab = label.encode("utf-8")
    base = M.rerun_destination(dest)
    audio = M.SOURCE_AUDIO if frames == 128 else M.ZERO
    final = M.apply(base, M.dup_ops(base, frames=frames, label=lab, audio=audio))
    return frames, lab, final


def check_row3(case, obs):
    frames, lab, final = row3_expected(case["source"], case["destination"])
    need(obs.get("call") == {"fn": "tape_dup", "result": "TAPE_OK", "more_work": False}, "dup did not complete")
    need(obs.get("source_label_hex") == lab.ljust(M.LABEL_BYTES, b"\0").hex(), "source fixture label")
    raw = obs.get("raw_after")
    need(isinstance(raw, dict) and set(raw) == {"P", "M", "A0h", "B0h"}, "raw_after blocks")
    got = {k: bytes.fromhex(v) for k, v in raw.items()}
    for copy in ("P", "M"):
        sb = got[copy]
        need(M.sb_valid(sb) and M.gen(sb) == 1, f"{copy}: completed copy is not sb_generation 1")
        need(sb[16] == 0 and sb[20:36] == M.B.FRESH_DUP_UUID, f"{copy}: state/UUID")
        need(int.from_bytes(sb[56:60], "little") == -(-frames // M.CF),
             f"{copy}: a_high_water != ceil(src_A.total_frames / CHUNK_FRAMES) = {-(-frames // M.CF)}")
        need(sb[M.LABEL_OFFSET:M.LABEL_OFFSET + M.LABEL_BYTES] == lab.ljust(M.LABEL_BYTES, b"\0"),
             f"{copy}: label is not a byte copy of the source label (V7-004)")
    for slot, side, seq in (("A0h", 0, 1), ("B0h", 1, 2)):
        h = got[slot]
        need(h[:8] == M.B.MAGIC_IDX and h[12] == side and int.from_bytes(h[8:12], "little") == seq,
             f"{slot}: side {h[12]} / sequence {int.from_bytes(h[8:12], 'little')}, want side {side} sequence {seq}")
        need(int.from_bytes(h[20:28], "little") == frames, f"{slot}: total_frames")
    need(got == {k: final[k] for k in got}, "completed metadata is not the tapefs §9.5 copy")
    for side in ("A", "B"):
        m = obs.get("mount_" + side)
        need(isinstance(m, dict) and m.get("result") == "TAPE_OK", f"completed copy does not mount on Side {side}")
        info = m.get("info", {})
        need(info.get("total_frames") == frames and info.get("side_b_valid") is True
             and info.get("label") == lab.decode("utf-8"),
             f"Side {side} info {info}")
    pcm = obs.get("mount_A", {}).get("pcm_sha256")
    need(pcm == obs.get("source_pcm_sha256") and isinstance(pcm, str), "copy does not render the source's audio")


# ------------------------------------------------------------------ planning

def iter_cases():
    idx = 0
    for shape in M.REPAIR_SHAPES:
        for mode, inject in M.injections(M.repair_ops(M.cartridge(*M.REPAIR_SHAPES[shape]))):
            yield {"index": idx, "row": 1, "shape": shape, "mode": mode, "inject": list(inject)}
            idx += 1
    for shape in M.RERUN_SHAPES:
        for mode, inject in M.injections(M.dup_ops(M.rerun_destination(shape))):
            yield {"index": idx, "row": 2, "shape": shape, "mode": mode, "inject": list(inject)}
            idx += 1
    for source, _, _ in ROW3_SOURCES:
        for dest in ROW3_DESTS:
            yield {"index": idx, "row": 3, "source": source, "destination": dest}
            idx += 1


@functools.lru_cache(maxsize=None)
def plan_census():
    h = hashlib.sha256()
    census = {"row1": 0, "row2": 0, "row3": 0, "row1_by_mode": {m: 0 for m in MODES},
              "row2_by_mode": {m: 0 for m in MODES}, "row1_by_shape": {}, "row2_by_shape": {}}
    for c in iter_cases():
        h.update((canonical(c) + "\n").encode())
        census[f"row{c['row']}"] += 1
        if c["row"] in (1, 2):
            census[f"row{c['row']}_by_mode"][c["mode"]] += 1
            key = f"row{c['row']}_by_shape"
            census[key][c["shape"]] = census[key].get(c["shape"], 0) + 1
    census["caseset_sha256"] = h.hexdigest()
    return census


def check(case, obs, trust_trace=False):
    _no_verdicts(obs)
    need(obs.get("schema") == SCHEMA and obs.get("index") == case["index"] and obs.get("row") == case["row"],
         "schema/case identity")
    if case["row"] in (1, 2):
        need(obs.get("shape") == case["shape"] and obs.get("mode") == case["mode"]
             and obs.get("inject") == case["inject"], "injection identity")
        (check_row1 if case["row"] == 1 else check_row2)(case, obs, trust_trace)
    else:
        need(obs.get("source") == case["source"] and obs.get("destination") == case["destination"], "row-3 identity")
        check_row3(case, obs)


def check_stream(lines, trust_trace=False):
    cases = iter_cases()
    n = 0
    for line in lines:
        case = next(cases, None)
        need(case is not None, "more observations than planned cases")
        check(case, json.loads(line), trust_trace)
        n += 1
    need(next(cases, None) is None, f"only {n} observations; plan has more cases")
    return n
