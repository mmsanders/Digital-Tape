#!/usr/bin/env python3
"""Independent oracle for the final WP-10 backlog rows (Verification #118, DRAFT-9)."""
from __future__ import annotations

import functools
import hashlib
import json

import dupmodel as DM
import model as M

SCHEMA = "wp10-final-r54-observation-v1"
MODES = ("flush_required", "write_through")
ROW1 = "WP10.counters.v5_015.reset_b_and_stage_clear_generation"
ROW2 = "WP10.headroom.zero_needed_reserved.empty_respool_each_counter_each_value"
ROW3 = "WP10.op.respool.post_crash_render"
ROW4 = "WP10.dup.rerun_crash"
ROWS = {1: ROW1, 2: ROW2, 3: ROW3, 4: ROW4}
FORBIDDEN_KEYS = {"verdict", "passed", "permitted", "expected", "outcome_ok", "row_ok", "same_audio",
                  "identity_ok", "selected_slot", "phase", "pass"}
F = M.F
CHUNK_REGION = range(F.LBA_CHUNK_BASE, F.LBA_MIRROR)
LANDED = range(M.BLOCK + 1)


def need(ok, why):
    if not ok:
        raise AssertionError(why)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _no_verdicts(value, where="observation"):
    if isinstance(value, dict):
        bad = FORBIDDEN_KEYS & set(value)
        need(not bad, f"{where} carries adapter-derived field(s) {sorted(bad)}")
        for k, v in value.items():
            _no_verdicts(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _no_verdicts(v, f"{where}[{i}]")


def _raw(obs_raw, name, blocks):
    v = obs_raw.get(name) if isinstance(obs_raw, dict) else None
    need(isinstance(v, str) and len(v) == blocks * M.BLOCK * 2, f"after_raw.{name} missing or wrong size")
    return bytes.fromhex(v)


def _chunk_writes(events):
    return [e for e in events if e.get("op") == "write" and e.get("lba") in CHUNK_REGION]


def _owned_writes_only(events, high, what):
    """Guardrail 05 / tapefs §7: ordinary Side-B writes stay at or above a_high_water."""
    for e in _chunk_writes(events):
        last = e["lba"] + e.get("count", 1) - 1
        need((e["lba"] - F.LBA_CHUNK_BASE) // F.CHUNK_BLOCKS >= high,
             f"{what}: chunk write at LBA {e['lba']} lies below a_high_water {high}")
        need(last in CHUNK_REGION, f"{what}: chunk write runs past the chunk store")


# ------------------------------------------------------------------ rows 1-2: contract cases

def _check_after_superblocks(raw, fixture, cleared):
    p, m = _raw(raw, "P", 1), _raw(raw, "M", 1)
    if cleared is None:
        need(p == M.block(fixture, F.LBA_PRIMARY) and m == M.block(fixture, F.LBA_MIRROR),
             "an index-only operation changed a superblock (sb_generation must not advance)")
        return
    want = F.build_superblock(generation=cleared, a_high_water=3, promote_stage=0, promote_staging_chunk=0)
    need(p == want and m == want, "stage clearing did not write promote_stage 0, staging 0, a_high_water "
                                  f"unchanged and sb_generation + 1 = {cleared:#x} to both copies")


def _check_stage_clear_order(events):
    """tapefs §8 stage clearing: partner first, candidate last, flushing after each (§4.6 healthy pair: mirror
    partner, primary candidate), before the call's first index or chunk write."""
    ev = [(e["op"], e.get("lba")) for e in events if e.get("op") in ("write", "flush")]
    need(ev[:4] == [("write", F.LBA_MIRROR), ("flush", None), ("write", F.LBA_PRIMARY), ("flush", None)],
         f"stage clearing order {ev[:4]}")


def _slot_state(raw, fixture, name):
    return M.parse_slot(_raw(raw, name, 2) + bytes(F.SLOT_BYTES - 2 * M.BLOCK))


def check_contract(case, obs):
    table = M.ROW1 if case["row"] == 1 else M.ROW2
    if case["row"] == 1:
        spec, side, fn, want, extra = table[case["case"]]
        fixture = M.row1_image(spec)
    else:
        args, want, extra = table[case["case"]]
        side, fn, fixture = "B", "tape_respool", M.row2_image(args)
    need(obs.get("case") == case["case"], "case identity")
    need(obs.get("image_sha256_before") == M.sha(fixture), "fixture image differs from the package's builder")
    need(obs.get("mount") == {"fn": "tape_mount", "side": side, "result": "TAPE_OK"}, "fixture did not mount")
    call = obs.get("call")
    need(isinstance(call, dict) and call.get("fn") == fn and call.get("result") == want,
         f"{fn} returned {call.get('result') if isinstance(call, dict) else call}, want {want}")
    if fn == "tape_respool" and want == "TAPE_OK":
        need(call.get("more_work") is False, "re-spool left more_work set")
    events = obs.get("events")
    need(isinstance(events, list), "events missing")
    writes = [e for e in events if e.get("op") == "write"]
    if want != "TAPE_OK" or extra.get("zero_write"):
        need(not writes, f"{fn} wrote {len(writes)} block(s); the specified result has zero writes")
        need(obs.get("image_sha256_after") == obs.get("image_sha256_before"), "media changed")
        return
    raw = obs.get("after_raw")
    high = 3 if "cleared" in extra else (1 if case["row"] == 2 else 2)
    _owned_writes_only(events, high, fn)
    _check_after_superblocks(raw, fixture, extra.get("cleared"))
    if "cleared" in extra:
        _check_stage_clear_order(events)
    for name in ("A0", "A1"):
        need(_raw(raw, name, 2) == M.block(fixture, M.SLOT_LBA[name], 2), f"{fn} changed Side A slot {name}")
    if "slot" in extra:
        name, seq, entries = extra["slot"]
        got = _slot_state(raw, fixture, name)
        need(got == {"sequence": seq, "side": 1, "entries": list(entries)},
             f"{name} after {fn}: {got}, want sequence {seq:#x} with Side A's entries")
        other = "B1" if name == "B0" else "B0"
        need(_raw(raw, other, 2) == M.block(fixture, M.SLOT_LBA[other], 2), f"{fn} changed {other}")
    if extra.get("slots_unchanged"):
        for name in ("B0", "B1"):
            need(_raw(raw, name, 2) == M.block(fixture, M.SLOT_LBA[name], 2), f"arm committed into {name}")
    if "respooled" in extra:
        name, seq, frames, min_chunk = extra["respooled"]
        got = _slot_state(raw, fixture, name)
        need(got is not None and got["sequence"] == seq and got["side"] == 1 and len(got["entries"]) == 1,
             f"re-spool commit {got}, want one entry at sequence {seq:#x} in {name}")
        first, start, n = got["entries"][0]
        need(start == 0 and n == frames and first >= min_chunk, f"re-spool layout {got['entries']}")
    if "respooled_index_only" in extra:
        s1, s2, frames, min_chunk = extra["respooled_index_only"]
        live = max((s for s in (_slot_state(raw, fixture, n) for n in ("B0", "B1")) if s), key=lambda s: s["sequence"])
        need(live["sequence"] in (s1, s2) and len(live["entries"]) == 1, f"re-spool live B {live}")
        first, start, n = live["entries"][0]
        need(start == 0 and n == frames and first >= min_chunk, f"re-spool layout {live['entries']}")


# ------------------------------------------------------------------ row 3: post-crash re-spool render

@functools.lru_cache(maxsize=None)
def row3_expected(fid):
    high, b_entries, _ = M.ROW3[fid]
    return {"high": high, "b_entries": len(b_entries), "total": sum(e[2] for e in b_entries),
            "pcm": M.sha(M.timeline(b_entries)), "a_pcm": M.sha(M.timeline(M.A_RS))}


def row3_injections(events):
    """Every write of the binding's own clean trace at landed 0..512, then every flush, in both modes."""
    writes = [i for i, e in enumerate(events) if e.get("op") == "write"]
    flushes = [i for i, e in enumerate(events) if e.get("op") == "flush"]
    out = []
    for mode in MODES:
        out += [(mode, ["write", k, landed], pos + 1) for k, pos in enumerate(writes) for landed in LANDED]
        out += [(mode, ["flush", j], pos + 1) for j, pos in enumerate(flushes)]
    return out


def _check_b_remount(m, exp, what):
    need(isinstance(m, dict) and m.get("result") == "TAPE_OK", f"{what}: Side B does not mount ({m})")
    info = m.get("info", {})
    need(info.get("total_frames") == exp["total"] and info.get("side_b_valid") is True,
         f"{what}: Side B info {info}")
    need(info.get("entry_count") in (exp["b_entries"], 1), f"{what}: entry_count {info.get('entry_count')}")
    need(m.get("pcm_sha256") == exp["pcm"], f"{what}: Side B does not render bit-identically to before")


def check_row3(case, obs):
    exp = row3_expected(case["fixture"])
    need(obs.get("fixture") == case["fixture"], "fixture identity")
    need(obs.get("image_sha256") == M.sha(M.row3_image(case["fixture"])), "fixture image")
    pre = obs.get("pre", {})
    _check_b_remount(pre.get("mount_B"), exp, "pre-operation")
    need(pre.get("mount_B", {}).get("info", {}).get("entry_count") == exp["b_entries"], "pre entry_count")
    need(pre.get("a_pcm_sha256") == exp["a_pcm"], "pre Side A render")
    clean = obs.get("clean", {})
    calls = clean.get("calls")
    need(isinstance(calls, list) and calls, "clean re-spool calls")
    for i, c in enumerate(calls):
        need(c == {"fn": "tape_respool", "block_budget": M.RS_BUDGET, "result": "TAPE_OK",
                   "more_work": i != len(calls) - 1}, f"clean re-spool call {i}: {c}")
    events = clean.get("events")
    need(isinstance(events, list) and all(e.get("op") in ("read", "write", "flush") for e in events), "clean events")
    writes = [i for i, e in enumerate(events) if e["op"] == "write"]
    flushes = [i for i, e in enumerate(events) if e["op"] == "flush"]
    need(writes and flushes and flushes[-1] > writes[-1], "clean re-spool left a write unflushed")
    _owned_writes_only(events, exp["high"], "clean re-spool")
    post = clean.get("post_mount_B")
    _check_b_remount(post, exp, "completed re-spool")
    need(post["info"]["entry_count"] == 1, "completed re-spool is not one entry")
    plan = row3_injections(events)
    crashes = obs.get("crashes")
    need(isinstance(crashes, list) and len(crashes) == len(plan),
         f"{len(crashes) if isinstance(crashes, list) else crashes} crash records, clean trace plans {len(plan)}")
    for (mode, inject, prefix_len), c in zip(plan, crashes):
        what = f"{case['fixture']} {mode} {inject}"
        need(c.get("mode") == mode and c.get("inject") == inject, f"{what}: injection identity")
        need(c.get("fired") is True and c.get("prefix_len") == prefix_len, f"{what}: did not fire at the plan point")
        _check_b_remount(c.get("remount_B"), exp, what)
        a = c.get("remount_A", {})
        need(a.get("result") == "TAPE_OK" and a.get("pcm_sha256") == exp["a_pcm"], f"{what}: Side A changed")
    return len(plan)


# ------------------------------------------------------------------ row 4: crashes inside the dup re-run

def dm_trace_sha256(ops):
    return DM.sha(canonical([{"op": "write", "lba": DM.TRACKED[o[1]], "count": 1, "data_sha256": DM.sha(o[2])}
                             if o[0] == "w" else {"op": "flush"} for o in ops]).encode())


def mount_expectation(img, side, writable):
    c = DM.classify(img, side, writable)
    exp = {"results": list(c["result"])}
    if c["result"] == ("TAPE_OK",):
        exp["info"] = {"uuid": c["uuid"], "free_chunks": c["free_chunks"], "total_frames": c["total_frames"],
                       "entry_count": c["entry_count"], "side_b_valid": c["side_b_valid"],
                       "needs_repair": c["needs_repair"]}
        rep = c["repair"]
        exp["repair_events"] = [] if rep is None else [
            {"op": "write", "lba": rep[0], "count": 1, "data_sha256": DM.sha(rep[1])}, {"op": "flush"}]
        if side == "A" and writable:
            exp["pcm_sha256"] = DM.rendered_sha256(img, c["layout"])
    return exp


def check_mount(m, img, side, writable, label):
    exp = mount_expectation(img, side, writable)
    need(isinstance(m, dict) and m.get("result") in exp["results"],
         f"{label}: {m.get('result') if isinstance(m, dict) else m} not in permitted {exp['results']}")
    if m["result"] != "TAPE_OK":
        need("info" not in m and m.get("repair_events") == [], f"{label}: failed mount reported info or wrote")
        return
    need(m.get("info") == exp["info"], f"{label}: info {m.get('info')} != {exp['info']}")
    need(m.get("repair_events") == exp["repair_events"], f"{label}: phase-4 repair events")
    if "pcm_sha256" in exp:
        need(m.get("pcm_sha256") == exp["pcm_sha256"], f"{label}: rendered audio is not the selected generation's")


OLD_PCM = DM.sha(DM.OLD_AUDIO)
NEW_PCM = DM.sha(DM.SOURCE_AUDIO)


def identity_violation(obs):
    """#116 finding, stated on observations alone: a writable Side-A remount showing the destination's previous
    identity with the source's audio, or the fresh identity with the previous album's audio."""
    m = obs.get("rw_A", {})
    if m.get("result") != "TAPE_OK":
        return None
    uuid, pcm = m.get("info", {}).get("uuid"), m.get("pcm_sha256")
    if uuid == M.NEW_UUID and pcm == OLD_PCM:
        return "fresh UUID playing the previous album"
    if uuid != M.NEW_UUID and pcm == NEW_PCM:
        return "previous UUID playing the source's copy"
    return None


# PM finding (V-R54-03). The frozen contract forces the violation above in exactly these re-run cells: the
# generation-exhausted fallback's candidate zero tore after 1 byte, so the re-run sees no valid superblock and
# takes the blank path (no barrier); its final primary write then tears after 1-12 bytes, which are identical
# in the fresh and previous superblocks, restoring the previous block with a valid CRC at sb_generation
# 0xFFFFFFFD, which tapefs §4.1 selects over the fresh copy at 1. Every other identity violation is a failure.
PM_FINDING_CELLS = {(shape, ("write", 1, 1), mode, ("write", 10, landed))
                    for shape in ("exhaustion_candidate", "exhaustion_equal_divergent")
                    for mode in MODES for landed in range(1, 13)}


def new_findings():
    return {"v_r54_03_resurrected_previous_superblock": 0}


@functools.lru_cache(maxsize=None)
def rerun_representatives():
    return tuple(M.rerun_representatives())


@functools.lru_cache(maxsize=None)
def _rep(shape, mode, inject):
    for r in rerun_representatives():
        if (r["shape"], r["first_mode"], tuple(r["first_inject"])) == (shape, mode, inject):
            return r
    raise AssertionError("no such representative")


@functools.lru_cache(maxsize=None)
def _rerun_ops(shape, mode, inject):
    return tuple(DM.dup_ops(_rep(shape, mode, inject)["crashed"]))


def check_row4(case, obs, findings, trust_trace=False):
    key = (case["shape"], case["first_mode"], tuple(case["first_inject"]))
    rep, ops = _rep(*key), list(_rerun_ops(*key))
    need(obs.get("shape") == case["shape"] and obs.get("first_mode") == case["first_mode"]
         and obs.get("first_inject") == case["first_inject"] and obs.get("mode") == case["mode"]
         and obs.get("inject") == case["inject"], "case identity")
    need(obs.get("first_durable_sha256") == DM.digest(rep["crashed"]),
         "first-run crash did not leave the representative interruption state")
    need(obs.get("source_sha256_before") == obs.get("source_sha256_after")
         and isinstance(obs.get("source_sha256_before"), str), "duplicate changed its source")
    need(obs.get("fired") is True, "planned re-run injection did not fire")
    inject = tuple(case["inject"])
    if not trust_trace:
        need(obs.get("trace_sha256") == dm_trace_sha256(DM.prefix(ops, inject)),
             "re-run write/flush trace is not tapefs §9.5 from the crashed state (item-5 classification)")
    violation = identity_violation(obs)
    cell = (case["shape"], tuple(case["first_inject"]), case["mode"], inject)
    need(violation is None or cell in PM_FINDING_CELLS, f"re-run crash: {violation}")
    images = {DM.digest(i): i for i in DM.possible_images(rep["crashed"], ops, inject, case["mode"])}
    img = images.get(obs.get("durable_sha256"))
    need(img is not None, "durable media after the interrupted re-run is not a permitted state")
    check_mount(obs.get("ro_A"), img, "A", False, "read-only Side-A remount")
    check_mount(obs.get("rw_A"), img, "A", True, "writable Side-A remount")
    check_mount(obs.get("rw_B"), img, "B", True, "writable Side-B remount")
    if violation:
        findings["v_r54_03_resurrected_previous_superblock"] += 1


# ------------------------------------------------------------------ planning

def iter_cases():
    idx = 0
    for cid in M.ROW1:
        yield {"index": idx, "row": 1, "kind": "contract", "case": cid}
        idx += 1
    for cid in M.ROW2:
        yield {"index": idx, "row": 2, "kind": "contract", "case": cid}
        idx += 1
    for fid in M.ROW3:
        yield {"index": idx, "row": 3, "kind": "respool_render", "fixture": fid}
        idx += 1
    for rep in rerun_representatives():
        for mode, inject in DM.injections(list(_rerun_ops(rep["shape"], rep["first_mode"], tuple(rep["first_inject"])))):
            yield {"index": idx, "row": 4, "kind": "rerun_crash", "shape": rep["shape"], "class": rep["class"],
                   "first_mode": rep["first_mode"], "first_inject": rep["first_inject"],
                   "mode": mode, "inject": list(inject)}
            idx += 1


@functools.lru_cache(maxsize=None)
def plan_census():
    h = hashlib.sha256()
    census = {"row1": 0, "row2": 0, "row3_groups": 0, "row4": 0, "row4_by_mode": {m: 0 for m in MODES},
              "row4_representatives": len(rerun_representatives()), "row4_by_class": {}}
    for c in iter_cases():
        h.update((canonical(c) + "\n").encode())
        census["row3_groups" if c["row"] == 3 else f"row{c['row']}"] += 1
        if c["row"] == 4:
            census["row4_by_mode"][c["mode"]] += 1
            k = f"{c['shape']}/{c['class'][0]}/{c['class'][1]}"
            census["row4_by_class"][k] = census["row4_by_class"].get(k, 0) + 1
    census["caseset_sha256"] = h.hexdigest()
    return census


def check(case, obs, trust_trace=False, findings=None):
    findings = new_findings() if findings is None else findings
    _no_verdicts(obs)
    need(obs.get("schema") == SCHEMA and obs.get("index") == case["index"] and obs.get("row") == case["row"]
         and obs.get("kind") == case["kind"], "schema/case identity")
    if case["row"] in (1, 2):
        check_contract(case, obs)
        return 0
    if case["row"] == 3:
        return check_row3(case, obs)
    check_row4(case, obs, findings, trust_trace)
    return 0


def check_stream(lines, trust_trace=False):
    cases = iter_cases()
    findings = new_findings()
    n = row3 = 0
    for line in lines:
        case = next(cases, None)
        need(case is not None, "more observations than planned cases")
        row3 += check(case, json.loads(line), trust_trace, findings)
        n += 1
    need(next(cases, None) is None, f"only {n} observations; plan has more cases")
    return n, row3, findings
