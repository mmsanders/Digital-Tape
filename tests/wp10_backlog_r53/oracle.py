#!/usr/bin/env python3
"""Independent oracle for WP-10 backlog rows 1-3 (Verification #110, DRAFT-9)."""
from __future__ import annotations

import functools
import hashlib
import json

import deps
import dupfrag as D

SCHEMA = "wp10-backlog-r53-observation-v1"
MODES = ("flush_required", "write_through")
RECORD_MODES = ("overwrite", "overdub", "splice")
ROW1, ROW2, ROW3 = (D.ROW, "WP10.universal.free_next_after_every_injection",
                    "WP10.session.record_audio_service_writes")
FORBIDDEN_KEYS = {"verdict", "passed", "permitted", "expected", "outcome_ok", "selected_copy", "row_ok",
                  "free_next_ok", "frontier"}
C = deps.C69
R = deps.R29B
# Row 3: 384 input frames = 3 blocks of s16 stereo, serviced at block_budget 1 (engine-api §6/§7).
REC_FRAMES, REC_BUDGET = 384, 1
REC_CHUNK = 2                       # free_next of the C69 record fixture (a_high_water 2, live B chunk 0)
REC_BLOCKS = tuple(C.fixture.LBA_CHUNK_BASE + REC_CHUNK * C.fixture.CHUNK_BLOCKS + k for k in range(3))


def need(ok, why):
    if not ok:
        raise AssertionError(why)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _no_verdicts(value, where="observation"):
    if isinstance(value, dict):
        bad = FORBIDDEN_KEYS & set(value)
        need(not bad, f"{where} carries adapter-derived field(s) {sorted(bad)}")
        for k, v in value.items():
            _no_verdicts(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _no_verdicts(v, f"{where}[{i}]")


def frontier(high, live_b_entries, degraded=False):
    """tapefs §7 / invariant 12: max(a_high_water, last+1 over live-B entries); a_high_water if degraded."""
    if degraded or live_b_entries is None:
        return high
    return max([high] + [f + (s + n - 1) // D.CF + 1 for f, s, n in live_b_entries])


# --------------------------------------------------------------------- row 1

def durable_digest(img):
    return sha(b"".join(img[n] for n in sorted(D.TRACKED)))


def trace_events(ops):
    out = []
    for o in ops:
        if o[0] == "f":
            out.append({"op": "flush"})
        else:
            lba = o[1] if isinstance(o[1], int) else D.TRACKED[o[1]]
            out.append({"op": "write", "lba": lba, "count": 1, "data_sha256": sha(o[2])})
    return out


def planned_prefix(scenario, inject, mutant=None):
    ops = D.transaction(scenario, mutant)
    if inject is None:
        return ops
    out, wk, fk = [], 0, 0
    for o in ops:
        out.append(o)
        if o[0] == "w":
            if inject[0] == "write" and inject[1] == wk:
                return out
            wk += 1
        else:
            if inject[0] == "flush" and inject[1] == fk:
                return out
            fk += 1
    raise AssertionError("injection beyond plan")


def dst_chunk_lbas(ops):
    return sorted({(o[1] if isinstance(o[1], int) else D.TRACKED[o[1]]) for o in ops if o[0] == "w"
                   and (o[1] if isinstance(o[1], int) else D.TRACKED[o[1]]) >= D.B.LBA_CHUNK_BASE
                   and (o[1] if isinstance(o[1], int) else D.TRACKED[o[1]]) != D.MIRROR})


def _check_mount(m, img, side, writable, label):
    exp = D.classify(img, side, writable)
    need(isinstance(m, dict), f"{label} missing")
    result = m.get("result")
    need(result in exp["result"], f"{label}: {result} not in permitted {list(exp['result'])}")
    if result != "TAPE_OK":
        need("info" not in m and m.get("repair_events") == [], f"{label}: failed mount reported info or wrote")
        return
    want = {"uuid": exp["uuid"], "free_chunks": exp["free_chunks"], "total_frames": exp["total_frames"],
            "entry_count": exp["entry_count"], "side_b_valid": exp["side_b_valid"],
            "needs_repair": exp["needs_repair"]}
    need(m.get("info") == want, f"{label}: info {m.get('info')} != {want}")
    rep = exp["repair"]
    want_ev = [] if rep is None else [{"op": "write", "lba": rep[0], "count": 1, "data_sha256": sha(rep[1])},
                                      {"op": "flush"}]
    need(m.get("repair_events") == want_ev, f"{label}: phase-4 repair events")
    if side == "A" and writable:
        need(m.get("pcm_sha256") == D.rendered_sha256(img, exp["layout"]),
             f"{label}: rendered Side A is not the selected generation's audio")


def check_row1(case, obs, trust_trace=False):
    scenario = case["scenario"]
    inject = tuple(case["inject"]) if case["kind"] == "crash" else None
    need(obs.get("source_sha256_before") == obs.get("source_sha256_after") and
         isinstance(obs.get("source_sha256_before"), str), "duplicate changed its source")
    len_a = -(-sum(e[2] for e in D.SRC_ENTRIES) // D.CF)
    lawful = set(range(D.B.LBA_CHUNK_BASE, D.B.LBA_CHUNK_BASE + len_a * D.B.CHUNK_BLOCKS))
    lbas = obs.get("dst_chunk_lbas")
    need(isinstance(lbas, list) and all(isinstance(x, int) for x in lbas), "dst_chunk_lbas missing")
    beyond = [x for x in lbas if x >= D.B.LBA_CHUNK_BASE + D.TOTAL_CHUNKS * D.B.CHUNK_BLOCKS]
    need(not beyond, f"destination chunk id >= total_chunks addressed at LBA {beyond}")
    need(set(lbas) <= lawful, f"copy not compacted to [0, {len_a}): destination LBAs {lbas}")
    if not trust_trace:
        need(obs.get("trace_sha256") == sha(canonical(trace_events(planned_prefix(scenario, inject))).encode()),
             "write/flush trace differs from tapefs §9.5 order")
    if inject is None:
        img = D.completed_image(scenario)
        need(obs.get("durable_sha256") == durable_digest(img), "completed media bytes")
        need(obs.get("call") == {"fn": "tape_dup", "result": "TAPE_OK", "more_work": False}, "dup did not complete")
    else:
        need(obs.get("mode") == case["mode"] and obs.get("inject") == case["inject"], "injection identity")
        need(obs.get("fired") is True, "planned injection did not fire")
        images = {durable_digest(i): i for i in D.possible_images(scenario, inject, case["mode"])}
        img = images.get(obs.get("durable_sha256"))
        need(img is not None, "durable media is not a state the durability model permits")
    _check_mount(obs.get("ro_A"), img, "A", False, "read-only Side-A remount")
    _check_mount(obs.get("rw_A"), img, "A", True, "writable Side-A remount")
    _check_mount(obs.get("rw_B"), img, "B", True, "writable Side-B remount")


# --------------------------------------------------------------------- row 2

@functools.lru_cache(maxsize=None)
def _c69_cases():
    return {c["case_index"]: c for c in C.planner.iter_cases()}


def c69_expectation(case_index):
    case = _c69_cases()[case_index]
    post = C.oracle.expected_snapshot(case, C.oracle._fixture_snapshot(case))
    side = "A" if case["family"] == "reset_b" and case["variant"] == "degraded_equal" else "B"
    st = C.media.inspect_snapshot(post, requested_side=side)
    out = {"post_snapshot_sha256": sha(canonical(post).encode()), "side": side, "result": st["mount_result"],
           "total_chunks": C.fixture.TOTAL_CHUNKS}
    if st["mount_result"] == "TAPE_OK":
        sb = st["superblock"]["selected"]
        live_b = None if st["degraded_b"] else st["side_b"]["selected"]["entries"]
        out["free_chunks"] = C.fixture.TOTAL_CHUNKS - frontier(sb["a_high_water"], live_b, st["degraded_b"])
    return out


@functools.lru_cache(maxsize=None)
def _r29b_cases():
    return {c["case_index"]: c for c in R.planner.iter_cases() if c["scope"] == "crash"}


def r29b_expectation(case_index):
    case = _r29b_cases()[case_index]
    post = R.oracle.expected_snapshot(case)
    st = R.media.inspect_snapshot(post)
    out = {"post_snapshot_sha256": sha(canonical(post).encode()), "side": "A", "result": st["mount_result"],
           "total_chunks": R.fixture.TOTAL_CHUNKS}
    if st["mount_result"] == "TAPE_OK":
        b0 = st["b0"]
        # R29-B's B0 head is either zero entries or the single entry {0, 0, total_frames}.
        live_b = [(0, 0, b0["total_frames"])] if b0.get("valid") and b0.get("entry_count") else []
        out["free_chunks"] = R.fixture.TOTAL_CHUNKS - frontier(st["superblock"]["selected"]["a_high_water"], live_b)
    return out


@functools.lru_cache(maxsize=None)
def row2_expectation(campaign, case_index):
    return c69_expectation(case_index) if campaign == "C69" else r29b_expectation(case_index)


def check_row2(case, obs):
    exp = row2_expectation(case["campaign"], case["case_index"])
    need(obs.get("campaign") == case["campaign"] and obs.get("case_index") == case["case_index"], "campaign case")
    need(obs.get("post_snapshot_sha256") == exp["post_snapshot_sha256"],
         "post-crash durable snapshot is not the accepted campaign's state for this injection")
    m = obs.get("remount")
    need(isinstance(m, dict) and m.get("side") == exp["side"] and m.get("result") == exp["result"], "remount")
    need(m.get("total_chunks") == exp["total_chunks"], "total_chunks")
    need(m.get("free_chunks") == exp["free_chunks"],
         f"free_chunks {m.get('free_chunks')}: frontier != max(a_high_water, live-B last+1) "
         f"(expected {exp['free_chunks']})")


# --------------------------------------------------------------------- row 3

@functools.lru_cache(maxsize=None)
def record_pre():
    img = bytes(C.fixture.record_fixture())
    meta = img[:C.fixture.BLOCK] + b"".join(
        img[lba * C.fixture.BLOCK:(lba + C.fixture.SLOT_BLOCKS) * C.fixture.BLOCK]
        for lba in (C.fixture.LBA_A0, C.fixture.LBA_A1, C.fixture.LBA_B0, C.fixture.LBA_B1)) + \
        img[C.fixture.LBA_MIRROR * C.fixture.BLOCK:(C.fixture.LBA_MIRROR + 1) * C.fixture.BLOCK]
    base = C.fixture.LBA_CHUNK_BASE * C.fixture.BLOCK
    chunk0 = img[base:base + C.fixture.CHUNK_BYTES]
    return {"meta_sha256": sha(meta), "chunk0_sha256": sha(chunk0), "pcm_sha256": sha(chunk0)}


def record_injections(n_flush):
    out = [["write", k, landed] for k in range(len(REC_BLOCKS)) for landed in range(513)]
    return out + [["flush", j] for j in range(n_flush)]


def check_clean_record(clean):
    events = clean.get("events")
    need(isinstance(events, list) and events, "clean service trace missing")
    writes = [e for e in events if e.get("op") == "write"]
    flushes = [i for i, e in enumerate(events) if e.get("op") == "flush"]
    need(all(e.get("op") in ("read", "write", "flush") for e in events), "unknown callback")
    need([(e.get("lba"), e.get("count")) for e in writes] == [(b, 1) for b in REC_BLOCKS],
         f"service writes {[(e.get('lba'), e.get('count')) for e in writes]} are not the three one-block "
         f"audio writes at free_next chunk {REC_CHUNK} (budget {REC_BUDGET})")
    last_write = max(i for i, e in enumerate(events) if e.get("op") == "write")
    need(flushes and flushes[-1] > last_write, "service did not make the audio durable before commit")
    need(clean.get("frames_owed_after") is False, "frames still owed after service")
    return len(flushes)


def check_row3(case, obs):
    need(obs.get("record_mode") == case["record_mode"] and obs.get("mode") == case["mode"], "record group identity")
    need(obs.get("setup") == [{"fn": "tape_mount", "side": "B", "result": "TAPE_OK"},
                              {"fn": "tape_seek", "frame": 0, "result": "TAPE_OK"},
                              {"fn": "tape_arm", "record_mode": case["record_mode"], "result": "TAPE_OK"},
                              {"fn": "tape_feed", "requested": REC_FRAMES, "accepted": REC_FRAMES,
                               "result": "TAPE_OK", "events_from_call": 0}], "record setup calls")
    clean = obs.get("clean")
    n_flush = check_clean_record(clean)
    events = clean["events"]
    positions = [i for i, e in enumerate(events) if e["op"] == "write"], \
                [i for i, e in enumerate(events) if e["op"] == "flush"]
    crashes = obs.get("crashes")
    want = record_injections(n_flush)
    need(isinstance(crashes, list) and [c.get("inject") for c in crashes] == want,
         f"crash census: every service write (3 x 513) and each of the {n_flush} observed flushes, in order")
    pre = record_pre()
    info = {"free_chunks": C.fixture.TOTAL_CHUNKS - REC_CHUNK, "total_frames": D.CF, "entry_count": 1,
            "side_b_valid": True, "needs_repair": False}
    for c in crashes:
        kind, k = c["inject"][0], c["inject"][1]
        pos = positions[0][k] if kind == "write" else positions[1][k]
        need(c.get("fired") is True and c.get("prefix_len") == pos + 1, f"injection {c['inject']} not fired at trace")
        need(c.get("meta_sha256") == pre["meta_sha256"],
             f"{c['inject']}: superblock/index metadata changed before commit (Side B not the pre generation)")
        need(c.get("chunk0_sha256") == pre["chunk0_sha256"], f"{c['inject']}: live audio chunk 0 changed")
        r = c.get("remount")
        need(r == {"side": "B", "result": "TAPE_OK", "info": info, "pcm_sha256": pre["pcm_sha256"]},
             f"{c['inject']}: remount {r} is not the intact pre-operation generation")


# ------------------------------------------------------------------ planning

@functools.lru_cache(maxsize=None)
def row2_cases():
    out = [("C69", i) for i in sorted(_c69_cases()) if c69_expectation(i)["result"] == "TAPE_OK"]
    out += [("R29B", i) for i in sorted(_r29b_cases()) if r29b_expectation(i)["result"] == "TAPE_OK"]
    return tuple(out)


def iter_cases():
    idx = 0
    for scenario in D.SCENARIOS:
        for mode, inject in D.injections(scenario):
            yield {"index": idx, "row": 1, "kind": "crash", "scenario": scenario, "mode": mode, "inject": list(inject)}
            idx += 1
    for scenario in D.SCENARIOS:
        yield {"index": idx, "row": 1, "kind": "complete", "scenario": scenario}
        idx += 1
    for campaign, ci in row2_cases():
        yield {"index": idx, "row": 2, "kind": "frontier", "campaign": campaign, "case_index": ci}
        idx += 1
    for rm in RECORD_MODES:
        for mode in MODES:
            yield {"index": idx, "row": 3, "kind": "record_group", "record_mode": rm, "mode": mode}
            idx += 1


@functools.lru_cache(maxsize=None)
def plan_census():
    h = hashlib.sha256()
    census = {"row1_crash": 0, "row1_complete": 0, "row2_frontier": 0, "row3_groups": 0,
              "row1_by_mode": {m: 0 for m in MODES}, "row2_by_campaign": {"C69": 0, "R29B": 0}, "row2_by_mode": {m: 0 for m in MODES},
              "row2_campaign_totals": {"C69": len(_c69_cases()), "R29B": len(_r29b_cases())}}
    for c in iter_cases():
        h.update((canonical(c) + "\n").encode())
        if c["row"] == 1:
            census["row1_crash" if c["kind"] == "crash" else "row1_complete"] += 1
            if c["kind"] == "crash":
                census["row1_by_mode"][c["mode"]] += 1
        elif c["row"] == 2:
            census["row2_frontier"] += 1
            census["row2_by_campaign"][c["campaign"]] += 1
            src = _c69_cases() if c["campaign"] == "C69" else _r29b_cases()
            census["row2_by_mode"][src[c["case_index"]]["mode"]] += 1
        else:
            census["row3_groups"] += 1
    census["caseset_sha256"] = h.hexdigest()
    return census


def check(case, obs, trust_trace=False):
    _no_verdicts(obs)
    need(obs.get("schema") == SCHEMA and obs.get("index") == case["index"] and obs.get("row") == case["row"]
         and obs.get("kind") == case["kind"], "schema/case identity")
    if case["row"] == 1:
        need(obs.get("scenario") == case["scenario"], "scenario identity")
        check_row1(case, obs, trust_trace)
    elif case["row"] == 2:
        check_row2(case, obs)
    else:
        check_row3(case, obs)


def check_stream(lines, trust_trace=False):
    cases = iter_cases()
    n = row3 = 0
    for line in lines:
        case = next(cases, None)
        need(case is not None, "more observations than planned cases")
        obs = json.loads(line)
        check(case, obs, trust_trace)
        if case["row"] == 3:
            row3 += len(obs["crashes"])
        n += 1
    need(next(cases, None) is None, f"only {n} observations; plan has more cases")
    return n, row3
